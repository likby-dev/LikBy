"""
tikible.repositories.sqlite.chat_session_repository
aiosqlite implementation of ChatSessionRepository.
"""

from datetime import datetime
import json
from typing import Optional
import aiosqlite
from tikible.domain.entities.chat_session import ChatSession
from tikible.domain.enums import SessionStatus, TerminationReason
from tikible.repositories.interfaces import ChatSessionRepository


class SqliteChatSessionRepository(ChatSessionRepository):
    """SQLite implementation of ChatSessionRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def get_by_id(self, session_id: str) -> Optional[ChatSession]:
        async with self._conn.execute(
            """
            SELECT id, user_a_id, user_b_id, status, match_score, match_metadata,
                   message_count, created_at, last_activity_at, ended_at,
                   ended_by_user_id, termination_reason
            FROM chat_sessions WHERE id = ?
            """,
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_active_by_user_id(self, user_id: str) -> Optional[ChatSession]:
        async with self._conn.execute(
            """
            SELECT id, user_a_id, user_b_id, status, match_score, match_metadata,
                   message_count, created_at, last_activity_at, ended_at,
                   ended_by_user_id, termination_reason
            FROM chat_sessions
            WHERE (user_a_id = ? OR user_b_id = ?) AND status = 'ACTIVE'
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def save(self, session: ChatSession) -> None:
        await self._conn.execute(
            """
            INSERT INTO chat_sessions (
                id, user_a_id, user_b_id, status, match_score, match_metadata,
                message_count, created_at, last_activity_at, ended_at,
                ended_by_user_id, termination_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                message_count = excluded.message_count,
                last_activity_at = excluded.last_activity_at,
                ended_at = excluded.ended_at,
                ended_by_user_id = excluded.ended_by_user_id,
                termination_reason = excluded.termination_reason
            """,
            (
                session.id,
                session.user_a_id,
                session.user_b_id,
                session.status.value,
                session.match_score,
                json.dumps(session.match_metadata),
                session.message_count,
                session.created_at.isoformat(),
                session.last_activity_at.isoformat(),
                session.ended_at.isoformat() if session.ended_at else None,
                session.ended_by_user_id,
                session.termination_reason.value if session.termination_reason else None,
            ),
        )
        await self._conn.commit()

    def _row_to_entity(self, row: tuple) -> ChatSession:
        return ChatSession(
            id=row[0],
            user_a_id=row[1],
            user_b_id=row[2],
            status=SessionStatus(row[3]),
            match_score=row[4],
            match_metadata=json.loads(row[5]),
            message_count=row[6],
            created_at=datetime.fromisoformat(row[7]),
            last_activity_at=datetime.fromisoformat(row[8]),
            ended_at=datetime.fromisoformat(row[9]) if row[9] else None,
            ended_by_user_id=row[10],
            termination_reason=TerminationReason(row[11]) if row[11] else None,
        )
