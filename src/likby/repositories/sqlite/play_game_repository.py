"""
likby.repositories.sqlite.play_game_repository
aiosqlite implementation of PlayGameRepository and DuelQuotaRepository.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import aiosqlite

from likby.domain.entities.play_game import (
    DuelQuotaUsage,
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
    SubscriptionTier,
)
from likby.repositories.interfaces import DuelQuotaRepository, PlayGameRepository


class SqlitePlayGameRepository(PlayGameRepository):
    """SQLite implementation of PlayGameRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save_session(self, session: PlayGameSession) -> None:
        await self._conn.execute(
            """
            INSERT INTO play_game_sessions (
                id, game_id, mode, status, rules_version, state_data,
                current_turn_user_id, round_number, max_rounds, winner_id,
                result_summary, created_at, started_at, completed_at,
                expires_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                state_data = excluded.state_data,
                current_turn_user_id = excluded.current_turn_user_id,
                round_number = excluded.round_number,
                winner_id = excluded.winner_id,
                result_summary = excluded.result_summary,
                started_at = excluded.started_at,
                completed_at = excluded.completed_at,
                metadata = excluded.metadata
            """,
            (
                session.id,
                session.game_id.value,
                session.mode.value,
                session.status.value,
                session.rules_version,
                json.dumps(session.state_data),
                session.current_turn_user_id,
                session.round_number,
                session.max_rounds,
                session.winner_id,
                session.result_summary,
                session.created_at.isoformat(),
                session.started_at.isoformat() if session.started_at else None,
                session.completed_at.isoformat() if session.completed_at else None,
                session.expires_at.isoformat() if session.expires_at else None,
                json.dumps(session.metadata),
            ),
        )
        await self._conn.commit()

    async def get_session(self, session_id: str) -> Optional[PlayGameSession]:
        async with self._conn.execute(
            """
            SELECT id, game_id, mode, status, rules_version, state_data,
                   current_turn_user_id, round_number, max_rounds, winner_id,
                   result_summary, created_at, started_at, completed_at,
                   expires_at, metadata
            FROM play_game_sessions WHERE id = ?
            """,
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return PlayGameSession(
                id=row[0],
                game_id=GameType(row[1]),
                mode=GameMode(row[2]),
                status=PlaySessionStatus(row[3]),
                rules_version=row[4],
                state_data=json.loads(row[5]) if row[5] else {},
                current_turn_user_id=row[6],
                round_number=row[7],
                max_rounds=row[8],
                winner_id=row[9],
                result_summary=row[10],
                created_at=datetime.fromisoformat(row[11]),
                started_at=datetime.fromisoformat(row[12]) if row[12] else None,
                completed_at=datetime.fromisoformat(row[13]) if row[13] else None,
                expires_at=datetime.fromisoformat(row[14]) if row[14] else None,
                metadata=json.loads(row[15]) if row[15] else {},
            )

    async def add_participant(self, participant: GameParticipant) -> None:
        await self._conn.execute(
            """
            INSERT INTO play_game_participants (
                game_session_id, user_id, role, joined_at, last_seen_at, final_score, is_winner
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(game_session_id, user_id) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                final_score = excluded.final_score,
                is_winner = excluded.is_winner
            """,
            (
                participant.game_session_id,
                participant.user_id,
                participant.role.value,
                participant.joined_at.isoformat(),
                participant.last_seen_at.isoformat(),
                participant.final_score,
                1 if participant.is_winner else 0,
            ),
        )
        await self._conn.commit()

    async def get_participants(self, session_id: str) -> List[GameParticipant]:
        participants = []
        async with self._conn.execute(
            """
            SELECT game_session_id, user_id, role, joined_at, last_seen_at, final_score, is_winner
            FROM play_game_participants WHERE game_session_id = ?
            """,
            (session_id,),
        ) as cursor:
            async for row in cursor:
                participants.append(
                    GameParticipant(
                        game_session_id=row[0],
                        user_id=row[1],
                        role=DuelParticipantRole(row[2]),
                        joined_at=datetime.fromisoformat(row[3]),
                        last_seen_at=datetime.fromisoformat(row[4]),
                        final_score=row[5],
                        is_winner=bool(row[6]),
                    )
                )
        return participants

    async def save_invitation(self, invitation: GameInvitation) -> None:
        await self._conn.execute(
            """
            INSERT INTO game_invitations (
                id, sender_id, recipient_id, game_id, status, session_id, expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                session_id = excluded.session_id
            """,
            (
                invitation.id,
                invitation.sender_id,
                invitation.recipient_id,
                invitation.game_id.value,
                invitation.status.value,
                invitation.session_id,
                invitation.expires_at.isoformat(),
                invitation.created_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_invitation(self, invitation_id: str) -> Optional[GameInvitation]:
        async with self._conn.execute(
            """
            SELECT id, sender_id, recipient_id, game_id, status, session_id, expires_at, created_at
            FROM game_invitations WHERE id = ?
            """,
            (invitation_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return GameInvitation(
                id=row[0],
                sender_id=row[1],
                recipient_id=row[2],
                game_id=GameType(row[3]),
                status=GameInvitationStatus(row[4]),
                session_id=row[5],
                expires_at=datetime.fromisoformat(row[6]),
                created_at=datetime.fromisoformat(row[7]),
            )

    async def get_pending_invitations_for_user(self, user_id: str) -> List[GameInvitation]:
        now_iso = datetime.now(timezone.utc).isoformat()
        invitations = []
        async with self._conn.execute(
            """
            SELECT id, sender_id, recipient_id, game_id, status, session_id, expires_at, created_at
            FROM game_invitations
            WHERE recipient_id = ? AND status = 'PENDING' AND expires_at > ?
            ORDER BY created_at DESC
            """,
            (user_id, now_iso),
        ) as cursor:
            async for row in cursor:
                invitations.append(
                    GameInvitation(
                        id=row[0],
                        sender_id=row[1],
                        recipient_id=row[2],
                        game_id=GameType(row[3]),
                        status=GameInvitationStatus(row[4]),
                        session_id=row[5],
                        expires_at=datetime.fromisoformat(row[6]),
                        created_at=datetime.fromisoformat(row[7]),
                    )
                )
        return invitations

    async def record_action(
        self,
        action_id: str,
        session_id: str,
        user_id: str,
        action_type: str,
        payload: dict,
        sequence_num: int,
    ) -> None:
        await self._conn.execute(
            """
            INSERT INTO game_action_events (
                id, game_session_id, user_id, action_type, action_payload, sequence_num, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                session_id,
                user_id,
                action_type,
                json.dumps(payload),
                sequence_num,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_actions(self, session_id: str) -> List[dict]:
        actions = []
        async with self._conn.execute(
            """
            SELECT id, user_id, action_type, action_payload, sequence_num, created_at
            FROM game_action_events WHERE game_session_id = ? ORDER BY sequence_num ASC
            """,
            (session_id,),
        ) as cursor:
            async for row in cursor:
                actions.append({
                    "id": row[0],
                    "user_id": row[1],
                    "action_type": row[2],
                    "payload": json.loads(row[3]) if row[3] else {},
                    "sequence_num": row[4],
                    "created_at": row[5],
                })
        return actions

    async def record_statistic(self, stat: GameStatistic) -> None:
        await self._conn.execute(
            """
            INSERT INTO game_statistics (
                user_id, game_id, games_played, wins, losses, draws, high_score, last_played_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, game_id) DO UPDATE SET
                games_played = games_played + excluded.games_played,
                wins = wins + excluded.wins,
                losses = losses + excluded.losses,
                draws = draws + excluded.draws,
                high_score = MAX(game_statistics.high_score, excluded.high_score),
                last_played_at = excluded.last_played_at
            """,
            (
                stat.user_id,
                stat.game_id.value,
                stat.games_played,
                stat.wins,
                stat.losses,
                stat.draws,
                stat.high_score,
                stat.last_played_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_statistic(self, user_id: str, game_id: GameType) -> Optional[GameStatistic]:
        async with self._conn.execute(
            """
            SELECT user_id, game_id, games_played, wins, losses, draws, high_score, last_played_at
            FROM game_statistics WHERE user_id = ? AND game_id = ?
            """,
            (user_id, game_id.value),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return GameStatistic(
                user_id=row[0],
                game_id=GameType(row[1]),
                games_played=row[2],
                wins=row[3],
                losses=row[4],
                draws=row[5],
                high_score=row[6],
                last_played_at=datetime.fromisoformat(row[7]),
            )

    async def get_user_statistics(self, user_id: str) -> List[GameStatistic]:
        stats = []
        async with self._conn.execute(
            """
            SELECT user_id, game_id, games_played, wins, losses, draws, high_score, last_played_at
            FROM game_statistics WHERE user_id = ?
            """,
            (user_id,),
        ) as cursor:
            async for row in cursor:
                stats.append(
                    GameStatistic(
                        user_id=row[0],
                        game_id=GameType(row[1]),
                        games_played=row[2],
                        wins=row[3],
                        losses=row[4],
                        draws=row[5],
                        high_score=row[6],
                        last_played_at=datetime.fromisoformat(row[7]),
                    )
                )
        return stats


class SqliteDuelQuotaRepository(DuelQuotaRepository):
    """SQLite implementation of DuelQuotaRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def record_consumption(self, usage: DuelQuotaUsage) -> bool:
        """
        Record consumed duel allowance idempotently.
        Returns True if recorded, False if already consumed for this session/user.
        """
        try:
            await self._conn.execute(
                """
                INSERT INTO duel_quota_usage (
                    id, user_id, game_session_id, subscription_tier_snapshot,
                    quota_period_start, quota_period_end, consumed_at, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    usage.id,
                    usage.user_id,
                    usage.game_session_id,
                    usage.subscription_tier_snapshot.value,
                    usage.quota_period_start,
                    usage.quota_period_end,
                    usage.consumed_at.isoformat(),
                    usage.idempotency_key,
                ),
            )
            await self._conn.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def count_duels_in_period(self, user_id: str, period_start: str) -> int:
        async with self._conn.execute(
            """
            SELECT COUNT(*) FROM duel_quota_usage
            WHERE user_id = ? AND quota_period_start = ?
            """,
            (user_id, period_start),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def has_consumed_for_session(self, user_id: str, session_id: str) -> bool:
        async with self._conn.execute(
            """
            SELECT 1 FROM duel_quota_usage
            WHERE user_id = ? AND game_session_id = ?
            """,
            (user_id, session_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None
