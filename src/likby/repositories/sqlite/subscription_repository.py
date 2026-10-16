"""
likby.repositories.sqlite.subscription_repository
aiosqlite implementation of SubscriptionRepository.
"""

from datetime import datetime
from typing import Optional
import aiosqlite
from likby.domain.entities.subscription import SubscriptionEntitlement
from likby.domain.enums import SubscriptionTier
from likby.repositories.interfaces import SubscriptionRepository


class SqliteSubscriptionRepository(SubscriptionRepository):
    """SQLite implementation of SubscriptionRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, entitlement: SubscriptionEntitlement) -> None:
        await self._conn.execute(
            """
            INSERT INTO subscriptions (
                user_id, tier, max_friends, daily_searches_limit,
                daily_requests_limit, starts_at, expires_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                tier = excluded.tier,
                max_friends = excluded.max_friends,
                daily_searches_limit = excluded.daily_searches_limit,
                daily_requests_limit = excluded.daily_requests_limit,
                starts_at = excluded.starts_at,
                expires_at = excluded.expires_at,
                is_active = excluded.is_active
            """,
            (
                entitlement.user_id,
                entitlement.tier.value,
                entitlement.max_friends,
                entitlement.daily_searches_limit,
                entitlement.daily_requests_limit,
                entitlement.starts_at.isoformat(),
                entitlement.expires_at.isoformat() if entitlement.expires_at else None,
                1 if entitlement.is_active else 0,
            ),
        )
        await self._conn.commit()

    async def get_by_user_id(self, user_id: str) -> Optional[SubscriptionEntitlement]:
        async with self._conn.execute(
            """
            SELECT user_id, tier, max_friends, daily_searches_limit,
                   daily_requests_limit, starts_at, expires_at, is_active
            FROM subscriptions WHERE user_id = ?
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    def _row_to_entity(self, row: tuple) -> SubscriptionEntitlement:
        return SubscriptionEntitlement(
            user_id=row[0],
            tier=SubscriptionTier(row[1]),
            max_friends=row[2],
            daily_searches_limit=row[3],
            daily_requests_limit=row[4],
            starts_at=datetime.fromisoformat(row[5]),
            expires_at=datetime.fromisoformat(row[6]) if row[6] else None,
            is_active=bool(row[7]),
        )
