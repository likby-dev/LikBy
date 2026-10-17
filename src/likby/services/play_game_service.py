"""
likby.services.play_game_service
Authoritative multiplayer game session coordinator, invitation state machine, and action dispatcher.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import uuid

from likby.domain.entities.play_game import (
    GAME_CATALOGUE,
    GameDefinition,
    GameInvitation,
    GameParticipant,
    GameStatistic,
    PlayGameSession,
)
from likby.domain.enums import (
    DuelParticipantRole,
    GameInvitationStatus,
    GameMode,
    GameType,
    PlaySessionStatus,
)
from likby.games.registry import get_game_engine
from likby.repositories.interfaces import (
    BlockRepository,
    PlayGameRepository,
    UserRepository,
)
from likby.services.gaming_entitlement_service import GamingEntitlementService


class PlayGameService:
    """Coordinates LikBy Play multiplayer duel sessions, solo games, invitations, and action dispatch."""

    def __init__(
        self,
        play_repo: PlayGameRepository,
        quota_service: GamingEntitlementService,
        user_repo: UserRepository,
        block_repo: Optional[BlockRepository] = None,
    ) -> None:
        self._play_repo = play_repo
        self._quota_service = quota_service
        self._user_repo = user_repo
        self._block_repo = block_repo

    def get_catalogue(self) -> List[GameDefinition]:
        """Returns the full 17-game catalogue."""
        return list(GAME_CATALOGUE.values())

    def get_game_definition(self, game_id: GameType) -> Optional[GameDefinition]:
        """Get catalogue entry for specific game."""
        return GAME_CATALOGUE.get(game_id)

    async def create_duel_invitation(
        self,
        sender_id: str,
        recipient_id: str,
        game_id: GameType,
    ) -> Tuple[bool, str, Optional[GameInvitation]]:
        """
        Create a time-limited duel challenge invitation.
        Verifies both players are valid, not blocked, and have remaining duel quota.
        Does NOT consume credits at invitation time.
        """
        if sender_id == recipient_id:
            return False, "You cannot challenge yourself to a duel.", None

        if self._quota_service.is_solo_game(game_id):
            return False, "Solo games cannot be played as a duel invitation.", None

        # Verify block status
        if self._block_repo and await self._block_repo.is_blocked(sender_id, recipient_id):
            return False, "Interaction unavailable between these accounts.", None

        # Verify sender eligibility
        can_a, reason_a, rem_a = await self._quota_service.can_start_duel(sender_id, game_id)
        if not can_a:
            return False, f"You cannot start a duel: {reason_a}", None

        # Verify recipient eligibility
        can_b, reason_b, rem_b = await self._quota_service.can_start_duel(recipient_id, game_id)
        if not can_b:
            return False, f"Opponent has reached their daily duel limit.", None

        now = datetime.now(timezone.utc)
        invitation = GameInvitation(
            id=f"inv_{uuid.uuid4().hex[:14]}",
            sender_id=sender_id,
            recipient_id=recipient_id,
            game_id=game_id,
            status=GameInvitationStatus.PENDING,
            expires_at=now + timedelta(minutes=10),
            created_at=now,
        )
        await self._play_repo.save_invitation(invitation)
        return True, "Duel invitation sent successfully.", invitation

    async def accept_invitation(
        self,
        invitation_id: str,
        recipient_id: str,
    ) -> Tuple[bool, str, Optional[PlayGameSession]]:
        """
        Accept duel invitation, atomically reserve credits from both participants,
        and instantiate active server-authoritative game session.
        """
        invitation = await self._play_repo.get_invitation(invitation_id)
        if not invitation:
            return False, "Invitation not found.", None

        if invitation.recipient_id != recipient_id:
            return False, "You are not authorized to accept this invitation.", None

        if invitation.status != GameInvitationStatus.PENDING:
            return False, f"Invitation is no longer pending (status: {invitation.status.value}).", None

        now = datetime.now(timezone.utc)
        if invitation.expires_at < now:
            invitation.status = GameInvitationStatus.EXPIRED
            await self._play_repo.save_invitation(invitation)
            return False, "Invitation has expired. Please request a new challenge.", None

        # 1. Verify eligibility of both participants before reserving session
        can_a, reason_a, _ = await self._quota_service.can_start_duel(invitation.sender_id, invitation.game_id)
        if not can_a:
            return False, f"Host cannot start duel: {reason_a}", None

        can_b, reason_b, _ = await self._quota_service.can_start_duel(invitation.recipient_id, invitation.game_id)
        if not can_b:
            return False, f"Challenger cannot start duel: {reason_b}", None

        engine = get_game_engine(invitation.game_id)
        if not engine:
            return False, f"Game engine for '{invitation.game_id.value}' not available.", None

        # 2. Instantiate and save session in STARTING state
        session_id = f"play_{uuid.uuid4().hex[:14]}"
        initial_state = engine.init_game_state(
            config={},
            player_ids=[invitation.sender_id, invitation.recipient_id],
        )

        game_defn = GAME_CATALOGUE[invitation.game_id]
        session = PlayGameSession(
            id=session_id,
            game_id=invitation.game_id,
            mode=game_defn.mode,
            status=PlaySessionStatus.STARTING,
            state_data=initial_state,
            current_turn_user_id=initial_state.get("current_turn") or invitation.sender_id,
            started_at=now,
            created_at=now,
        )
        await self._play_repo.save_session(session)

        # 3. Atomically consume 1 credit from each player
        consumed, quota_msg = await self._quota_service.consume_duel_credits_for_match(
            session_id=session_id,
            user_a_id=invitation.sender_id,
            user_b_id=invitation.recipient_id,
        )
        if not consumed:
            session.status = PlaySessionStatus.CANCELLED
            await self._play_repo.save_session(session)
            return False, f"Could not start duel: {quota_msg}", None

        # 4. Transition to ACTIVE
        session.status = PlaySessionStatus.ACTIVE
        await self._play_repo.save_session(session)

        # Register participants
        await self._play_repo.add_participant(
            GameParticipant(
                game_session_id=session_id,
                user_id=invitation.sender_id,
                role=DuelParticipantRole.HOST,
            )
        )
        await self._play_repo.add_participant(
            GameParticipant(
                game_session_id=session_id,
                user_id=invitation.recipient_id,
                role=DuelParticipantRole.CHALLENGER,
            )
        )

        invitation.status = GameInvitationStatus.ACCEPTED
        invitation.session_id = session_id
        await self._play_repo.save_invitation(invitation)

        return True, "Invitation accepted. Duel session active!", session

    async def reject_invitation(
        self,
        invitation_id: str,
        recipient_id: str,
    ) -> Tuple[bool, str]:
        """Reject duel challenge without consuming any credits."""
        invitation = await self._play_repo.get_invitation(invitation_id)
        if not invitation:
            return False, "Invitation not found."

        if invitation.recipient_id != recipient_id:
            return False, "Unauthorized."

        invitation.status = GameInvitationStatus.REJECTED
        await self._play_repo.save_invitation(invitation)
        return True, "Invitation rejected. No credits were consumed."

    async def start_solo_game(
        self,
        user_id: str,
        game_id: GameType,
    ) -> Tuple[bool, str, Optional[PlayGameSession]]:
        """
        Start a solo game experience.
        Solo games NEVER consume duel credits and are completely unlimited for every tier.
        """
        if not self._quota_service.is_solo_game(game_id):
            return False, f"Game '{game_id.value}' is a multiplayer duel, not a solo game.", None

        engine = get_game_engine(game_id)
        if not engine:
            return False, "Solo game engine not available.", None

        now = datetime.now(timezone.utc)
        session_id = f"play_solo_{uuid.uuid4().hex[:14]}"
        state = engine.init_game_state(config={}, player_ids=[user_id])

        session = PlayGameSession(
            id=session_id,
            game_id=game_id,
            mode=GameMode.SOLO,
            status=PlaySessionStatus.ACTIVE,
            state_data=state,
            current_turn_user_id=user_id,
            started_at=now,
            created_at=now,
        )
        await self._play_repo.save_session(session)

        await self._play_repo.add_participant(
            GameParticipant(
                game_session_id=session_id,
                user_id=user_id,
                role=DuelParticipantRole.SOLO_PLAYER,
            )
        )
        return True, "Solo game started successfully.", session

    async def submit_action(
        self,
        session_id: str,
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[Dict[str, Any]], Optional[str]]:
        """
        Submit a player move or event to the active game engine.
        Validates participant authorization, updates state, and persists match results on completion.
        """
        session = await self._play_repo.get_session(session_id)
        if not session:
            return False, "Game session not found.", None, None

        if session.status != PlaySessionStatus.ACTIVE:
            return False, f"Session is not active (current status: {session.status.value}).", None, None

        # Verify participant
        participants = await self._play_repo.get_participants(session_id)
        part_user_ids = [p.user_id for p in participants]
        if user_id not in part_user_ids:
            return False, "You are not an authorized participant in this game session.", None, None

        engine = get_game_engine(session.game_id)
        if not engine:
            return False, "Engine not found.", None, None

        # Execute action in engine
        ok, msg, new_state, winner = engine.process_action(
            current_state=session.state_data,
            user_id=user_id,
            action_type=action_type,
            action_payload=action_payload,
        )
        if not ok:
            return False, msg, None, None

        session.state_data = new_state
        if new_state.get("current_turn"):
            session.current_turn_user_id = new_state["current_turn"]

        # Record action event
        await self._play_repo.record_action(
            action_id=f"act_{uuid.uuid4().hex[:14]}",
            session_id=session_id,
            user_id=user_id,
            action_type=action_type,
            payload=action_payload,
            sequence_num=len(await self._play_repo.get_actions(session_id)) + 1,
        )

        # Check match completion
        if winner or new_state.get("status") == "COMPLETED" or new_state.get("game_over"):
            session.status = PlaySessionStatus.COMPLETED
            session.winner_id = winner
            session.completed_at = datetime.now(timezone.utc)
            session.result_summary = msg

            # Update participant stats
            for p in participants:
                is_win = p.user_id == winner
                p.is_winner = is_win
                await self._play_repo.add_participant(p)

                stat = GameStatistic(
                    user_id=p.user_id,
                    game_id=session.game_id,
                    games_played=1,
                    wins=1 if is_win else 0,
                    losses=1 if (winner and winner not in (p.user_id, "DRAW", "COOP_SUCCESS", "COOP_VICTORY")) else 0,
                    draws=1 if winner in ("DRAW", "COOP_SUCCESS", "COOP_VICTORY") else 0,
                    high_score=new_state.get("score", 0),
                    last_played_at=datetime.now(timezone.utc),
                )
                await self._play_repo.record_statistic(stat)

        await self._play_repo.save_session(session)
        sanitized = engine.get_sanitized_state_for_player(new_state, user_id)
        return True, msg, sanitized, winner

    async def get_authorized_session_state(
        self,
        session_id: str,
        user_id: str,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Retrieve sanitized player state ensuring private opponent data is concealed."""
        session = await self._play_repo.get_session(session_id)
        if not session:
            return False, "Session not found.", None

        participants = await self._play_repo.get_participants(session_id)
        if user_id not in [p.user_id for p in participants]:
            return False, "Unauthorized: you are not a participant in this game.", None

        engine = get_game_engine(session.game_id)
        if not engine:
            return True, "OK", session.state_data

        clean_state = engine.get_sanitized_state_for_player(session.state_data, user_id)
        return True, "OK", {
            "session_id": session.id,
            "game_id": session.game_id.value,
            "mode": session.mode.value,
            "status": session.status.value,
            "current_turn": session.current_turn_user_id,
            "winner_id": session.winner_id,
            "state": clean_state,
            "game_state": clean_state,
            "participants": [{"user_id": p.user_id, "role": p.role.value, "is_winner": p.is_winner} for p in participants],
        }

    async def request_rematch(
        self,
        session_id: str,
        user_id: str,
    ) -> Tuple[bool, str, Optional[PlayGameSession]]:
        """
        Create a new duel session between the same participants.
        A rematch is a new duel and consumes new credits from both players.
        """
        old_session = await self._play_repo.get_session(session_id)
        if not old_session:
            return False, "Original game session not found.", None

        participants = await self._play_repo.get_participants(session_id)
        if len(participants) < 2:
            return False, "Cannot rematch a non-duel session.", None

        user_ids = [p.user_id for p in participants]
        if user_id not in user_ids:
            return False, "Unauthorized.", None

        p1, p2 = user_ids[0], user_ids[1]
        new_session_id = f"play_{uuid.uuid4().hex[:14]}"

        # Consume new credits for rematch
        consumed, msg = await self._quota_service.consume_duel_credits_for_match(
            session_id=new_session_id,
            user_a_id=p1,
            user_b_id=p2,
        )
        if not consumed:
            return False, f"Rematch failed: {msg}", None

        engine = get_game_engine(old_session.game_id)
        now = datetime.now(timezone.utc)
        new_state = engine.init_game_state(config={}, player_ids=[p1, p2])

        new_session = PlayGameSession(
            id=new_session_id,
            game_id=old_session.game_id,
            mode=old_session.mode,
            status=PlaySessionStatus.ACTIVE,
            state_data=new_state,
            current_turn_user_id=new_state.get("current_turn") or p1,
            started_at=now,
            created_at=now,
        )
        await self._play_repo.save_session(new_session)

        await self._play_repo.add_participant(
            GameParticipant(game_session_id=new_session_id, user_id=p1, role=DuelParticipantRole.HOST)
        )
        await self._play_repo.add_participant(
            GameParticipant(game_session_id=new_session_id, user_id=p2, role=DuelParticipantRole.CHALLENGER)
        )
        return True, "Rematch started! New duel credits reserved.", new_session
