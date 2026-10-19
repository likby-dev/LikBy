"""
likby.services.game_matchmaking_service
Authoritative multiplayer matchmaking queue service for LikBy GameVerse.
Supports random matchmaking queues per game mode, invitation tokens,
status transitions, connection timeouts, and fair pairing.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from likby.domain.entities.play_game import GAME_CATALOGUE, GameInvitation, PlayGameSession
from likby.domain.enums import GameMode, GameType, PlaySessionStatus
from likby.services.gaming_entitlement_service import GamingEntitlementService
from likby.services.play_game_service import PlayGameService

logger = logging.getLogger(__name__)


class MatchQueueState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    QUEUED = "QUEUED"
    MATCHED = "MATCHED"
    READY = "READY"
    PLAYING = "PLAYING"
    RECONNECTING = "RECONNECTING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class QueueEntry:
    def __init__(self, user_id: str, game_type: GameType) -> None:
        self.ticket_id: str = f"gq_{uuid.uuid4().hex[:12]}"
        self.user_id: str = user_id
        self.game_type: GameType = game_type
        self.enqueued_at: datetime = datetime.now(timezone.utc)
        self.state: MatchQueueState = MatchQueueState.QUEUED
        self.matched_session_id: Optional[str] = None
        self.partner_user_id: Optional[str] = None


class GameMatchmakingService:
    """
    In-memory matchmaking engine with thread-safe queue pairing,
    timeout sweeps, and entitlement validation.
    """

    def __init__(
        self,
        play_service: PlayGameService,
        quota_service: GamingEntitlementService,
    ) -> None:
        self._play_service = play_service
        self._quota_service = quota_service
        self._queues: Dict[GameType, List[QueueEntry]] = {g: [] for g in GameType}
        self._user_tickets: Dict[str, QueueEntry] = {}
        self._lock = asyncio.Lock()

    async def enqueue_player(
        self, user_id: str, game_type: GameType
    ) -> Tuple[bool, str, Optional[QueueEntry]]:
        """Add player to the matchmaking queue for a specified duel game."""
        # Solo games cannot be matched
        if self._quota_service.is_solo_game(game_type):
            return False, "Solo games do not use the multiplayer matchmaking queue.", None

        # Verify duel eligibility and remaining credits
        can_play, reason, rem = await self._quota_service.can_start_duel(user_id, game_type)
        if not can_play:
            return False, reason, None

        async with self._lock:
            # Cancel any existing active ticket for this user
            if user_id in self._user_tickets:
                old_entry = self._user_tickets[user_id]
                if old_entry.state == MatchQueueState.QUEUED:
                    self._remove_from_queue(old_entry)

            entry = QueueEntry(user_id=user_id, game_type=game_type)
            self._queues[game_type].append(entry)
            self._user_tickets[user_id] = entry
            logger.info("Enqueued user %s for game %s (ticket: %s)", user_id, game_type.value, entry.ticket_id)

            # Try immediate pairing
            match_found, match_session = await self._try_match(game_type)
            if match_found:
                return True, "Match found!", self._user_tickets.get(user_id)

            return True, "Searching for an opponent...", entry

    async def cancel_player(self, user_id: str) -> bool:
        """Cancel queue search for a player."""
        async with self._lock:
            if user_id in self._user_tickets:
                entry = self._user_tickets[user_id]
                if entry.state == MatchQueueState.QUEUED:
                    entry.state = MatchQueueState.CANCELLED
                    self._remove_from_queue(entry)
                    del self._user_tickets[user_id]
                    logger.info("Cancelled queue for user %s", user_id)
                    return True
        return False

    def get_status(self, user_id: str) -> Dict[str, Any]:
        """Get current matchmaking status for a user."""
        entry = self._user_tickets.get(user_id)
        if not entry:
            return {
                "state": MatchQueueState.DISCONNECTED.value,
                "ticket_id": None,
                "session_id": None,
                "partner_id": None,
            }

        return {
            "state": entry.state.value,
            "ticket_id": entry.ticket_id,
            "game_id": entry.game_type.value,
            "session_id": entry.matched_session_id,
            "partner_id": entry.partner_user_id,
            "wait_seconds": int((datetime.now(timezone.utc) - entry.enqueued_at).total_seconds()),
        }

    async def _try_match(self, game_type: GameType) -> Tuple[bool, Optional[PlayGameSession]]:
        """Pair two eligible waiting players in the queue."""
        queue = self._queues[game_type]
        waiting = [e for e in queue if e.state == MatchQueueState.QUEUED]
        if len(waiting) < 2:
            return False, None

        player_a = waiting[0]
        player_b = waiting[1]

        # Ensure both are distinct users
        if player_a.user_id == player_b.user_id:
            return False, None

        # Verify both players still have quota
        can_a, _, _ = await self._quota_service.can_start_duel(player_a.user_id, game_type)
        can_b, _, _ = await self._quota_service.can_start_duel(player_b.user_id, game_type)
        if not can_a:
            player_a.state = MatchQueueState.FAILED
            self._remove_from_queue(player_a)
            return False, None
        if not can_b:
            player_b.state = MatchQueueState.FAILED
            self._remove_from_queue(player_b)
            return False, None

        # Create session via PlayGameService invitation or direct session
        now = datetime.now(timezone.utc)
        invitation = GameInvitation(
            id=f"inv_mm_{uuid.uuid4().hex[:12]}",
            sender_id=player_a.user_id,
            recipient_id=player_b.user_id,
            game_id=game_type,
            expires_at=now + timedelta(minutes=5),
        )
        await self._play_service._play_repo.save_invitation(invitation)

        ok, msg, session = await self._play_service.accept_invitation(invitation.id, player_b.user_id)
        if not ok or not session:
            logger.error("Matchmaking session creation failed: %s", msg)
            return False, None

        # Transition state
        player_a.state = MatchQueueState.MATCHED
        player_a.matched_session_id = session.id
        player_a.partner_user_id = player_b.user_id

        player_b.state = MatchQueueState.MATCHED
        player_b.matched_session_id = session.id
        player_b.partner_user_id = player_a.user_id

        self._remove_from_queue(player_a)
        self._remove_from_queue(player_b)
        logger.info(
            "Match created: session=%s between %s and %s for %s",
            session.id,
            player_a.user_id,
            player_b.user_id,
            game_type.value,
        )
        return True, session

    def _remove_from_queue(self, entry: QueueEntry) -> None:
        try:
            self._queues[entry.game_type].remove(entry)
        except ValueError:
            pass
