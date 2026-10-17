"""
likby.repositories.postgres.user_repository
asyncpg PostgreSQL / Supabase implementation of UserRepository.
"""

from datetime import datetime, timezone
from typing import Optional
import asyncpg
from likby.domain.entities.user import User
from likby.domain.enums import UserState, UserStatus
from likby.repositories.interfaces import UserRepository


class PostgresUserRepository(UserRepository):
    """PostgreSQL implementation of UserRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_id(self, user_id: str) -> Optional[User]:
        query = """
            SELECT id, telegram_id, unique_id, state, status, age_verified, terms_accepted_at,
                   karma_score, report_count, ban_reason, banned_at, last_active_at, created_at, updated_at
            FROM users WHERE id = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        query = """
            SELECT id, telegram_id, unique_id, state, status, age_verified, terms_accepted_at,
                   karma_score, report_count, ban_reason, banned_at, last_active_at, created_at, updated_at
            FROM users WHERE telegram_id = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, telegram_id)
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_by_unique_id(self, unique_id: str) -> Optional[User]:
        clean = unique_id.strip().lstrip("@").lower()
        query = """
            SELECT id, telegram_id, unique_id, state, status, age_verified, terms_accepted_at,
                   karma_score, report_count, ban_reason, banned_at, last_active_at, created_at, updated_at
            FROM users WHERE LOWER(unique_id) = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, clean)
            if not row:
                return None
            return self._row_to_entity(row)

    async def save(self, user: User) -> None:
        query = """
            INSERT INTO users (
                id, telegram_id, unique_id, state, status, age_verified, terms_accepted_at,
                karma_score, report_count, ban_reason, banned_at, last_active_at, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (id) DO UPDATE SET
                unique_id = COALESCE(EXCLUDED.unique_id, users.unique_id),
                state = EXCLUDED.state,
                status = EXCLUDED.status,
                age_verified = EXCLUDED.age_verified,
                terms_accepted_at = EXCLUDED.terms_accepted_at,
                karma_score = EXCLUDED.karma_score,
                report_count = EXCLUDED.report_count,
                ban_reason = EXCLUDED.ban_reason,
                banned_at = EXCLUDED.banned_at,
                last_active_at = EXCLUDED.last_active_at,
                updated_at = EXCLUDED.updated_at
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                user.id,
                user.telegram_id,
                user.unique_id,
                user.state.value,
                user.status.value,
                user.age_verified,
                user.terms_accepted_at,
                user.karma_score,
                user.report_count,
                user.ban_reason,
                user.banned_at,
                user.last_active_at,
                user.created_at,
                user.updated_at,
            )

    def _row_to_entity(self, row: asyncpg.Record) -> User:
        return User(
            id=row["id"],
            telegram_id=row["telegram_id"],
            unique_id=row["unique_id"],
            state=UserState(row["state"]),
            status=UserStatus(row["status"]),
            age_verified=bool(row["age_verified"]),
            terms_accepted_at=row["terms_accepted_at"],
            karma_score=row["karma_score"],
            report_count=row["report_count"],
            ban_reason=row["ban_reason"],
            banned_at=row["banned_at"],
            last_active_at=row["last_active_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
