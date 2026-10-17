"""
likby.repositories.postgres.friendship_repository
asyncpg PostgreSQL / Supabase implementation of FriendshipRepository.
"""

from typing import List, Optional
import asyncpg
from likby.domain.entities.friendship import Friendship
from likby.repositories.interfaces import FriendshipRepository


class PostgresFriendshipRepository(FriendshipRepository):
    """PostgreSQL implementation of FriendshipRepository enforcing canonical pairs."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_users(self, user_a_id: str, user_b_id: str) -> Optional[Friendship]:
        low, high = (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)
        query = "SELECT id, user_low_id, user_high_id, created_at FROM friendships WHERE user_low_id = $1 AND user_high_id = $2"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, low, high)
            if not row:
                return None
            return self._row_to_entity(row)

    async def list_by_user_id(self, user_id: str) -> List[Friendship]:
        query = "SELECT id, user_low_id, user_high_id, created_at FROM friendships WHERE user_low_id = $1 OR user_high_id = $1 ORDER BY created_at DESC"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, user_id)
            return [self._row_to_entity(r) for r in rows]

    async def count_by_user_id(self, user_id: str) -> int:
        query = "SELECT COUNT(*) as cnt FROM friendships WHERE user_low_id = $1 OR user_high_id = $1"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
            return row["cnt"] if row else 0

    async def save(self, friendship: Friendship) -> None:
        query = """
            INSERT INTO friendships (id, user_low_id, user_high_id, created_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_low_id, user_high_id) DO NOTHING
        """
        async with self._pool.acquire() as conn:
            await conn.execute(query, friendship.id, friendship.user_low_id, friendship.user_high_id, friendship.created_at)

    async def delete(self, friendship_id: str) -> bool:
        query = "DELETE FROM friendships WHERE id = $1"
        async with self._pool.acquire() as conn:
            res = await conn.execute(query, friendship_id)
            return "DELETE 1" in res

    def _row_to_entity(self, row: asyncpg.Record) -> Friendship:
        return Friendship(
            id=row["id"],
            user_low_id=row["user_low_id"],
            user_high_id=row["user_high_id"],
            created_at=row["created_at"],
        )
