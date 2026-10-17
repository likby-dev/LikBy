"""
likby.repositories.sqlite.subscription_repository
aiosqlite implementation of SubscriptionRepository.
"""

from datetime import datetime
from typing import Optional
import aiosqlite
from likby.domain.entities.subscription import PLAN_SPECS, SubscriptionEntitlement
from likby.domain.enums import EntitlementSource, SubscriptionTier
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
                daily_requests_limit, starts_at, expires_at, is_active,
                source, source_transaction_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                tier = excluded.tier,
                max_friends = excluded.max_friends,
                daily_searches_limit = excluded.daily_searches_limit,
                daily_requests_limit = excluded.daily_requests_limit,
                starts_at = excluded.starts_at,
                expires_at = excluded.expires_at,
                is_active = excluded.is_active,
                source = excluded.source,
                source_transaction_id = excluded.source_transaction_id
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
                entitlement.source.value if hasattr(entitlement.source, "value") else str(entitlement.source),
                entitlement.source_transaction_id,
            ),
        )
        await self._conn.commit()

    async def get_by_user_id(self, user_id: str) -> Optional[SubscriptionEntitlement]:
        async with self._conn.execute(
            """
            SELECT user_id, tier, max_friends, daily_searches_limit,
                   daily_requests_limit, starts_at, expires_at, is_active,
                   source, source_transaction_id
            FROM subscriptions WHERE user_id = ?
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def reap_expired_subscriptions(self, now: Optional[datetime] = None) -> int:
        target_time = (now or datetime.now()).isoformat()
        async with self._conn.execute(
            """
            UPDATE subscriptions
            SET tier = 'BASE', is_active = 1, expires_at = NULL, source = 'FREE'
            WHERE is_active = 1 AND tier != 'BASE' AND expires_at IS NOT NULL AND expires_at < ?
            """,
            (target_time,),
        ) as cursor:
            count = cursor.rowcount
        await self._conn.commit()
        return count

    def _row_to_entity(self, row: tuple) -> SubscriptionEntitlement:
        source_val = EntitlementSource.FREE
        if len(row) > 8 and row[8]:
            try:
                source_val = EntitlementSource(row[8])
            except ValueError:
                source_val = EntitlementSource.FREE

        source_txn = row[9] if len(row) > 9 else None
        tier = SubscriptionTier(row[1])
        spec = PLAN_SPECS.get(tier, PLAN_SPECS[SubscriptionTier.BASE])

        return SubscriptionEntitlement(
            user_id=row[0],
            tier=tier,
            max_friends=row[2],
            daily_searches_limit=row[3],
            daily_requests_limit=row[4],
            daily_likes_limit=spec["daily_likes_limit"],
            daily_games_limit=spec["daily_games_limit"],
            daily_icebreakers_limit=spec["daily_icebreakers_limit"],
            daily_uploads_limit=spec.get("daily_uploads_limit", 20),
            daily_receive_limit=spec.get("daily_receive_limit", 10),
            max_image_size_bytes=spec.get("max_image_size_bytes", 20971520),
            max_video_size_bytes=spec.get("max_video_size_bytes", 20971520),
            pending_requests_limit=spec["pending_requests_limit"],
            profile_boosts_remaining=spec["profile_boosts"],
            starts_at=datetime.fromisoformat(row[5]),
            expires_at=datetime.fromisoformat(row[6]) if row[6] else None,
            is_active=bool(row[7]),
            source=source_val,
            source_transaction_id=source_txn,
        )
