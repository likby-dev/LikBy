"""
likby.repositories.sqlite.payment_order_repository
aiosqlite implementation of PaymentOrderRepository.
"""

from datetime import datetime
from typing import List, Optional
import aiosqlite
from likby.domain.entities.payment import PaymentOrder
from likby.domain.enums import PaymentOrderStatus, PaymentProviderType
from likby.repositories.interfaces import PaymentOrderRepository


class SqlitePaymentOrderRepository(PaymentOrderRepository):
    """SQLite implementation of PaymentOrderRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, order: PaymentOrder) -> None:
        await self._conn.execute(
            """
            INSERT INTO payment_orders (
                id, internal_order_id, user_id, plan_id, provider,
                provider_order_id, amount_minor_units, currency, status,
                idempotency_key, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                provider_order_id = excluded.provider_order_id,
                expires_at = excluded.expires_at
            """,
            (
                order.id,
                order.internal_order_id,
                order.user_id,
                order.plan_id,
                order.provider.value,
                order.provider_order_id,
                order.amount_minor_units,
                order.currency,
                order.status.value,
                order.idempotency_key or f"idemp_{order.id}",
                order.created_at.isoformat(),
                order.expires_at.isoformat() if order.expires_at else None,
            ),
        )
        await self._conn.commit()

    async def get_by_id(self, order_id: str) -> Optional[PaymentOrder]:
        async with self._conn.execute(
            "SELECT id, internal_order_id, user_id, plan_id, provider, provider_order_id, amount_minor_units, currency, status, idempotency_key, created_at, expires_at "
            "FROM payment_orders WHERE id = ?",
            (order_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_entity(row) if row else None

    async def get_by_internal_order_id(self, internal_order_id: str) -> Optional[PaymentOrder]:
        async with self._conn.execute(
            "SELECT id, internal_order_id, user_id, plan_id, provider, provider_order_id, amount_minor_units, currency, status, idempotency_key, created_at, expires_at "
            "FROM payment_orders WHERE internal_order_id = ?",
            (internal_order_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_entity(row) if row else None

    async def get_by_provider_order_id(
        self, provider: PaymentProviderType, provider_order_id: str
    ) -> Optional[PaymentOrder]:
        async with self._conn.execute(
            "SELECT id, internal_order_id, user_id, plan_id, provider, provider_order_id, amount_minor_units, currency, status, idempotency_key, created_at, expires_at "
            "FROM payment_orders WHERE provider = ? AND provider_order_id = ?",
            (provider.value, provider_order_id),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_entity(row) if row else None

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[PaymentOrder]:
        async with self._conn.execute(
            "SELECT id, internal_order_id, user_id, plan_id, provider, provider_order_id, amount_minor_units, currency, status, idempotency_key, created_at, expires_at "
            "FROM payment_orders WHERE idempotency_key = ?",
            (idempotency_key,),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_entity(row) if row else None

    async def get_user_orders(self, user_id: str, limit: int = 20) -> List[PaymentOrder]:
        orders = []
        async with self._conn.execute(
            "SELECT id, internal_order_id, user_id, plan_id, provider, provider_order_id, amount_minor_units, currency, status, idempotency_key, created_at, expires_at "
            "FROM payment_orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ) as cursor:
            async for row in cursor:
                orders.append(self._row_to_entity(row))
        return orders

    def _row_to_entity(self, row: tuple) -> PaymentOrder:
        return PaymentOrder(
            id=row[0],
            internal_order_id=row[1],
            user_id=row[2],
            plan_id=row[3],
            provider=PaymentProviderType(row[4]),
            provider_order_id=row[5],
            amount_minor_units=row[6],
            currency=row[7],
            status=PaymentOrderStatus(row[8]),
            idempotency_key=row[9],
            created_at=datetime.fromisoformat(row[10]),
            expires_at=datetime.fromisoformat(row[11]) if row[11] else None,
        )
