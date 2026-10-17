"""
likby.repositories.postgres.chat_session_repository
asyncpg PostgreSQL / Supabase implementation of ChatSessionRepository.
"""

from datetime import datetime, timezone
import json
from typing import List, Optional
import asyncpg
from likby.domain.entities.chat_session import ChatSession
from likby.domain.enums import SessionStatus, TerminationReason
from likby.repositories.interfaces import ChatSessionRepository


class PostgresChatSessionRepository(ChatSessionRepository):
    """PostgreSQL implementation of ChatSessionRepository for relational session metadata."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_id(self, session_id: str) -> Optional[ChatSession]:
        query = """
            SELECT id, user_a_id, user_b_id, status, termination_reason,
                   started_at, ended_at, message_count, last_activity_at, metadata
            FROM chat_sessions WHERE id = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, session_id)
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_active_by_user_id(self, user_id: str) -> Optional[ChatSession]:
        query = """
            SELECT id, user_a_id, user_b_id, status, termination_reason,
                   started_at, ended_at, message_count, last_activity_at, metadata
            FROM chat_sessions
            WHERE (user_a_id = $1 OR user_b_id = $1) AND status = 'ACTIVE'
            ORDER BY started_at DESC LIMIT 1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
            if not row:
                return None
            return self._row_to_entity(row)

    async def save(self, session: ChatSession) -> None:
        query = """
            INSERT INTO chat_sessions (
                id, user_a_id, user_b_id, status, termination_reason,
                started_at, ended_at, last_activity_at, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                termination_reason = EXCLUDED.termination_reason,
                ended_at = EXCLUDED.ended_at,
                last_activity_at = EXCLUDED.last_activity_at,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
        """
        meta_json = json.dumps(session.metadata) if isinstance(session.metadata, dict) else session.metadata or "{}"
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                session.id,
                session.user_a_id,
                session.user_b_id,
                session.status.value,
                session.termination_reason.value if session.termination_reason else None,
                session.started_at,
                session.ended_at,
                session.last_activity_at,
                meta_json,
            )

    async def list_recent(self, limit: int = 50) -> List[ChatSession]:
        query = """
            SELECT id, user_a_id, user_b_id, status, termination_reason,
                   started_at, ended_at, last_activity_at, metadata
            FROM chat_sessions
            ORDER BY started_at DESC LIMIT $1
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, limit)
            return [self._row_to_entity(r) for r in rows]

    def _row_to_entity(self, row: asyncpg.Record) -> ChatSession:
        term = TerminationReason(row["termination_reason"]) if row["termination_reason"] else None
        meta = row.get("metadata")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        elif meta is None:
            meta = {}

        return ChatSession(
            id=row["id"],
            user_a_id=row["user_a_id"],
            user_b_id=row["user_b_id"],
            status=SessionStatus(row["status"]),
            termination_reason=term,
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            message_count=row.get("message_count", 0) or 0,
            last_activity_at=row["last_activity_at"],
            metadata=meta,
        )
