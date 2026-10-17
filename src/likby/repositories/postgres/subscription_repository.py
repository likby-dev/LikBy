"""
likby.repositories.postgres.subscription_repository
asyncpg PostgreSQL / Supabase implementation of SubscriptionRepository.
"""

from typing import Optional
import asyncpg
from likby.domain.entities.subscription import UserSubscription
from likby.domain.enums import SubscriptionTier
from likby.repositories.interfaces import SubscriptionRepository


class PostgresSubscriptionRepository(SubscriptionRepository):
    """PostgreSQL implementation of SubscriptionRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_user_id(self, user_id: str) -> Optional[UserSubscription]:
        query = """
            SELECT id, user_id, tier, is_active, started_at, expires_at, plan_name, created_at, updated_at
            FROM user_subscriptions
            WHERE user_id = $1 AND is_active = TRUE
            ORDER BY started_at DESC LIMIT 1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
            if not row:
                return None
            return self._row_to_entity(row)

    async def save(self, subscription: UserSubscription) -> None:
        query = """
            INSERT INTO user_subscriptions (
                id, user_id, tier, is_active, started_at, expires_at, plan_name, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO UPDATE SET
                tier = EXCLUDED.tier,
                is_active = EXCLUDED.is_active,
                expires_at = EXCLUDED.expires_at,
                plan_name = EXCLUDED.plan_name,
                updated_at = EXCLUDED.updated_at
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                subscription.id,
                subscription.user_id,
                subscription.tier.value,
                subscription.is_active,
                subscription.started_at,
                subscription.expires_at,
                subscription.plan_name,
                subscription.created_at,
                subscription.updated_at,
            )

    def _row_to_entity(self, row: asyncpg.Record) -> UserSubscription:
        return UserSubscription(
            id=row["id"],
            user_id=row["user_id"],
            tier=SubscriptionTier(row["tier"]),
            is_active=bool(row["is_active"]),
            started_at=row["started_at"],
            expires_at=row["expires_at"],
            plan_name=row["plan_name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
