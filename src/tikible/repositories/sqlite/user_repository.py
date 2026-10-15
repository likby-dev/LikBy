"""
tikible.repositories.sqlite.user_repository
aiosqlite implementation of UserRepository.
"""

from datetime import datetime
from typing import Optional
import aiosqlite
from tikible.domain.entities.user import User
from tikible.domain.enums import UserState, UserStatus
from tikible.repositories.interfaces import UserRepository


class SqliteUserRepository(UserRepository):
    """SQLite implementation of UserRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def get_by_id(self, user_id: str) -> Optional[User]:
        async with self._conn.execute(
            "SELECT id, telegram_id, state, status, age_verified, terms_accepted_at, "
            "karma_score, report_count, ban_reason, banned_at, last_active_at, created_at, updated_at "
            "FROM users WHERE id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        async with self._conn.execute(
            "SELECT id, telegram_id, state, status, age_verified, terms_accepted_at, "
            "karma_score, report_count, ban_reason, banned_at, last_active_at, created_at, updated_at "
            "FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def save(self, user: User) -> None:
        await self._conn.execute(
            """
            INSERT INTO users (
                id, telegram_id, state, status, age_verified, terms_accepted_at,
                karma_score, report_count, ban_reason, banned_at, last_active_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                state = excluded.state,
                status = excluded.status,
                age_verified = excluded.age_verified,
                terms_accepted_at = excluded.terms_accepted_at,
                karma_score = excluded.karma_score,
                report_count = excluded.report_count,
                ban_reason = excluded.ban_reason,
                banned_at = excluded.banned_at,
                last_active_at = excluded.last_active_at,
                updated_at = excluded.updated_at
            """,
            (
                user.id,
                user.telegram_id,
                user.state.value,
                user.status.value,
                1 if user.age_verified else 0,
                user.terms_accepted_at.isoformat() if user.terms_accepted_at else None,
                user.karma_score,
                user.report_count,
                user.ban_reason,
                user.banned_at.isoformat() if user.banned_at else None,
                user.last_active_at.isoformat(),
                user.created_at.isoformat(),
                user.updated_at.isoformat(),
            ),
        )
        await self._conn.commit()

    def _row_to_entity(self, row: tuple) -> User:
        return User(
            id=row[0],
            telegram_id=row[1],
            state=UserState(row[2]),
            status=UserStatus(row[3]),
            age_verified=bool(row[4]),
            terms_accepted_at=datetime.fromisoformat(row[5]) if row[5] else None,
            karma_score=row[6],
            report_count=row[7],
            ban_reason=row[8],
            banned_at=datetime.fromisoformat(row[9]) if row[9] else None,
            last_active_at=datetime.fromisoformat(row[10]),
            created_at=datetime.fromisoformat(row[11]),
            updated_at=datetime.fromisoformat(row[12]),
        )
