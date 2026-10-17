"""
likby.repositories.sqlite.subscription_plan_repository
aiosqlite implementation of SubscriptionPlanRepository.
"""

from datetime import datetime, timezone
import json
from typing import List, Optional
import aiosqlite
from likby.domain.entities.subscription import ProviderPrice, SubscriptionPlan
from likby.domain.enums import PaymentProviderType
from likby.repositories.interfaces import SubscriptionPlanRepository


class SqliteSubscriptionPlanRepository(SubscriptionPlanRepository):
    """SQLite implementation of plan catalog and provider prices."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def get_all_active_plans(self) -> List[SubscriptionPlan]:
        plans = []
        async with self._conn.execute(
            "SELECT id, code, display_name, active, entitlements_json, version, created_at, updated_at "
            "FROM subscription_plans WHERE active = 1 ORDER BY version ASC"
        ) as cursor:
            async for row in cursor:
                plans.append(
                    SubscriptionPlan(
                        id=row[0],
                        code=row[1],
                        display_name=row[2],
                        active=bool(row[3]),
                        entitlements_json=json.loads(row[4]) if row[4] else {},
                        version=row[5],
                        created_at=datetime.fromisoformat(row[6]),
                        updated_at=datetime.fromisoformat(row[7]),
                    )
                )
        return plans

    list_active_plans = get_all_active_plans

    async def get_plan_by_code(self, code: str) -> Optional[SubscriptionPlan]:
        async with self._conn.execute(
            "SELECT id, code, display_name, active, entitlements_json, version, created_at, updated_at "
            "FROM subscription_plans WHERE code = ?",
            (code.upper(),),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return SubscriptionPlan(
                id=row[0],
                code=row[1],
                display_name=row[2],
                active=bool(row[3]),
                entitlements_json=json.loads(row[4]) if row[4] else {},
                version=row[5],
                created_at=datetime.fromisoformat(row[6]),
                updated_at=datetime.fromisoformat(row[7]),
            )

    async def get_prices_for_plan(
        self,
        plan_id: str,
        provider: Optional[PaymentProviderType] = None,
    ) -> List[ProviderPrice]:
        prices = []
        query = "SELECT id, plan_id, provider, provider_product_id, amount_minor_units, currency, duration_seconds, active, environment, created_at FROM provider_prices WHERE plan_id = ? AND active = 1"
        params: list = [plan_id]
        if provider:
            query += " AND provider = ?"
            params.append(provider.value)

        async with self._conn.execute(query, params) as cursor:
            async for row in cursor:
                prices.append(
                    ProviderPrice(
                        id=row[0],
                        plan_id=row[1],
                        provider=PaymentProviderType(row[2]),
                        provider_product_id=row[3],
                        amount_minor_units=row[4],
                        currency=row[5],
                        duration_seconds=row[6],
                        active=bool(row[7]),
                        environment=row[8],
                        created_at=datetime.fromisoformat(row[9]),
                    )
                )
        return prices

    async def get_price_by_id(self, price_id: str) -> Optional[ProviderPrice]:
        async with self._conn.execute(
            "SELECT id, plan_id, provider, provider_product_id, amount_minor_units, currency, duration_seconds, active, environment, created_at "
            "FROM provider_prices WHERE id = ?",
            (price_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return ProviderPrice(
                id=row[0],
                plan_id=row[1],
                provider=PaymentProviderType(row[2]),
                provider_product_id=row[3],
                amount_minor_units=row[4],
                currency=row[5],
                duration_seconds=row[6],
                active=bool(row[7]),
                environment=row[8],
                created_at=datetime.fromisoformat(row[9]),
            )
