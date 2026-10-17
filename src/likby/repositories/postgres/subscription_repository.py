"""
likby.repositories.postgres.subscription_repository
asyncpg PostgreSQL / Supabase implementation of SubscriptionRepository.
"""

from datetime import datetime, timezone
from typing import Optional
import asyncpg
from likby.domain.entities.subscription import PLAN_SPECS, SubscriptionEntitlement
from likby.domain.enums import EntitlementSource, SubscriptionTier
from likby.repositories.interfaces import SubscriptionRepository


class PostgresSubscriptionRepository(SubscriptionRepository):
    """PostgreSQL implementation of SubscriptionRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_user_id(self, user_id: str) -> Optional[SubscriptionEntitlement]:
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

    async def save(self, entitlement: SubscriptionEntitlement) -> None:
        sub_id = entitlement.id or f"sub_{entitlement.user_id}"
        tier_str = entitlement.tier.value if hasattr(entitlement.tier, "value") else str(entitlement.tier)
        plan_name = f"LikBy {tier_str.title()}"
        started_at = entitlement.starts_at or datetime.now(timezone.utc)
        now_dt = datetime.now(timezone.utc)

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
                sub_id,
                entitlement.user_id,
                tier_str,
                entitlement.is_active,
                started_at,
                entitlement.expires_at,
                plan_name,
                now_dt,
                now_dt,
            )

    def _row_to_entity(self, row: asyncpg.Record) -> SubscriptionEntitlement:
        raw_tier = row["tier"]
        normalized = raw_tier.replace("LIKBY_", "").upper()
        try:
            tier = SubscriptionTier(normalized)
        except ValueError:
            tier = SubscriptionTier.BASE

        spec = PLAN_SPECS.get(tier, PLAN_SPECS[SubscriptionTier.BASE])
        return SubscriptionEntitlement(
            id=row["id"],
            user_id=row["user_id"],
            tier=tier,
            max_friends=spec["max_friends"],
            daily_likes_limit=spec["daily_likes_limit"],
            daily_searches_limit=spec["daily_searches_limit"],
            daily_requests_limit=spec["daily_requests_limit"],
            daily_games_limit=spec["daily_games_limit"],
            daily_icebreakers_limit=spec["daily_icebreakers_limit"],
            daily_uploads_limit=spec.get("daily_uploads_limit", 20),
            daily_receive_limit=spec.get("daily_receive_limit", 10),
            max_image_size_bytes=spec.get("max_image_size_bytes", 20971520),
            max_video_size_bytes=spec.get("max_video_size_bytes", 20971520),
            pending_requests_limit=spec["pending_requests_limit"],
            profile_boosts_remaining=spec["profile_boosts"],
            starts_at=row["started_at"],
            expires_at=row["expires_at"],
            is_active=bool(row["is_active"]),
            source=EntitlementSource.PURCHASE if tier != SubscriptionTier.BASE else EntitlementSource.FREE,
        )

