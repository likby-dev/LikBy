"""
likby.repositories.sqlite.like_repository
aiosqlite implementation of LikeRepository.
"""

from datetime import datetime
from typing import List, Optional
import aiosqlite
from likby.domain.entities.like import Like
from likby.repositories.interfaces import LikeRepository


class SqliteLikeRepository(LikeRepository):
    """SQLite implementation of LikeRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, like: Like) -> None:
        await self._conn.execute(
            """
            INSERT INTO likes (id, sender_id, target_id, session_id, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(sender_id, target_id) DO UPDATE SET
                is_active = excluded.is_active,
                session_id = COALESCE(excluded.session_id, likes.session_id)
            """,
            (
                like.id,
                like.sender_id,
                like.target_id,
                like.session_id,
                1 if like.is_active else 0,
                like.created_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_like(self, sender_id: str, target_id: str) -> Optional[Like]:
        async with self._conn.execute(
            """
            SELECT id, sender_id, target_id, session_id, is_active, created_at
            FROM likes
            WHERE sender_id = ? AND target_id = ?
            """,
            (sender_id, target_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_incoming_likes(self, target_id: str) -> List[Like]:
        async with self._conn.execute(
            """
            SELECT id, sender_id, target_id, session_id, is_active, created_at
            FROM likes
            WHERE target_id = ? AND is_active = 1
            ORDER BY created_at DESC
            """,
            (target_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_entity(r) for r in rows]

    def _row_to_entity(self, row: tuple) -> Like:
        return Like(
            id=row[0],
            sender_id=row[1],
            target_id=row[2],
            session_id=row[3],
            is_active=bool(row[4]),
            created_at=datetime.fromisoformat(row[5]),
        )
