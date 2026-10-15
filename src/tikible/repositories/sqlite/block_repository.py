"""
tikible.repositories.sqlite.block_repository
aiosqlite implementation of BlockRepository.
"""

from datetime import datetime
import aiosqlite
from tikible.domain.entities.block import UserBlock
from tikible.repositories.interfaces import BlockRepository


class SqliteBlockRepository(BlockRepository):
    """SQLite implementation of BlockRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def is_blocked(self, user_a_id: str, user_b_id: str) -> bool:
        """Check if either user has blocked the other (bilateral barrier)."""
        async with self._conn.execute(
            """
            SELECT 1 FROM user_blocks
            WHERE (blocker_id = ? AND blocked_id = ?)
               OR (blocker_id = ? AND blocked_id = ?)
            LIMIT 1
            """,
            (user_a_id, user_b_id, user_b_id, user_a_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None

    async def save(self, block: UserBlock) -> None:
        await self._conn.execute(
            """
            INSERT INTO user_blocks (id, blocker_id, blocked_id, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(blocker_id, blocked_id) DO NOTHING
            """,
            (
                block.id,
                block.blocker_id,
                block.blocked_id,
                block.created_at.isoformat(),
            ),
        )
        await self._conn.commit()
