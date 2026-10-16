"""
likby.repositories.sqlite.friendship_repository
aiosqlite implementation of FriendshipRepository.
"""

from datetime import datetime
from typing import List, Optional
import aiosqlite
from likby.domain.entities.friendship import Friendship
from likby.domain.enums import FriendshipStatus
from likby.repositories.interfaces import FriendshipRepository


class SqliteFriendshipRepository(FriendshipRepository):
    """SQLite implementation of FriendshipRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, friendship: Friendship) -> None:
        await self._conn.execute(
            """
            INSERT INTO friendships (id, user_a_id, user_b_id, status, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                friendship.id,
                friendship.user_a_id,
                friendship.user_b_id,
                friendship.status.value,
                friendship.source,
                friendship.created_at.isoformat(),
                friendship.updated_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_by_id(self, friendship_id: str) -> Optional[Friendship]:
        async with self._conn.execute(
            """
            SELECT id, user_a_id, user_b_id, status, source, created_at, updated_at
            FROM friendships WHERE id = ?
            """,
            (friendship_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_friendship(self, user_1: str, user_2: str) -> Optional[Friendship]:
        u_a, u_b = sorted([user_1, user_2])
        canonical_id = f"frd_{u_a}_{u_b}"
        return await self.get_by_id(canonical_id)

    async def get_user_friends(self, user_id: str) -> List[Friendship]:
        async with self._conn.execute(
            """
            SELECT id, user_a_id, user_b_id, status, source, created_at, updated_at
            FROM friendships
            WHERE (user_a_id = ? OR user_b_id = ?) AND status = 'ACTIVE'
            ORDER BY updated_at DESC
            """,
            (user_id, user_id),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_entity(r) for r in rows]

    async def count_user_friends(self, user_id: str) -> int:
        async with self._conn.execute(
            """
            SELECT COUNT(*) FROM friendships
            WHERE (user_a_id = ? OR user_b_id = ?) AND status = 'ACTIVE'
            """,
            (user_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    def _row_to_entity(self, row: tuple) -> Friendship:
        return Friendship(
            id=row[0],
            user_a_id=row[1],
            user_b_id=row[2],
            status=FriendshipStatus(row[3]),
            source=row[4],
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6]),
        )
