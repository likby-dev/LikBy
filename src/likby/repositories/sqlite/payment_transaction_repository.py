"""
likby.repositories.sqlite.payment_transaction_repository
aiosqlite implementation of PaymentTransactionRepository.
"""

from datetime import datetime
from typing import List, Optional
import aiosqlite
from likby.domain.entities.payment import PaymentTransaction
from likby.domain.enums import PaymentProviderType, PaymentTransactionStatus
from likby.repositories.interfaces import PaymentTransactionRepository


class SqlitePaymentTransactionRepository(PaymentTransactionRepository):
    """SQLite implementation of PaymentTransactionRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, transaction: PaymentTransaction) -> None:
        await self._conn.execute(
            """
            INSERT INTO payment_transactions (
                id, order_id, provider, provider_payment_id, provider_order_id,
                provider_signature_verified, amount_minor_units, currency,
                payment_status, captured_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider_payment_id) DO UPDATE SET
                payment_status = excluded.payment_status
            """,
            (
                transaction.id,
                transaction.order_id,
                transaction.provider.value,
                transaction.provider_payment_id,
                transaction.provider_order_id,
                1 if transaction.provider_signature_verified else 0,
                transaction.amount_minor_units,
                transaction.currency,
                transaction.payment_status.value,
                transaction.captured_at.isoformat(),
                transaction.created_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_by_id(self, transaction_id: str) -> Optional[PaymentTransaction]:
        async with self._conn.execute(
            "SELECT id, order_id, provider, provider_payment_id, provider_order_id, provider_signature_verified, amount_minor_units, currency, payment_status, captured_at, created_at "
            "FROM payment_transactions WHERE id = ?",
            (transaction_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_entity(row) if row else None

    async def get_by_provider_payment_id(self, provider_payment_id: str) -> Optional[PaymentTransaction]:
        async with self._conn.execute(
            "SELECT id, order_id, provider, provider_payment_id, provider_order_id, provider_signature_verified, amount_minor_units, currency, payment_status, captured_at, created_at "
            "FROM payment_transactions WHERE provider_payment_id = ?",
            (provider_payment_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_entity(row) if row else None

    async def get_by_order_id(self, order_id: str) -> List[PaymentTransaction]:
        txns = []
        async with self._conn.execute(
            "SELECT id, order_id, provider, provider_payment_id, provider_order_id, provider_signature_verified, amount_minor_units, currency, payment_status, captured_at, created_at "
            "FROM payment_transactions WHERE order_id = ? ORDER BY created_at DESC",
            (order_id,),
        ) as cursor:
            async for row in cursor:
                txns.append(self._row_to_entity(row))
        return txns

    async def list_by_user(self, user_id: str) -> List[PaymentTransaction]:
        txns = []
        async with self._conn.execute(
            """
            SELECT pt.id, pt.order_id, pt.provider, pt.provider_payment_id, pt.provider_order_id,
                   pt.provider_signature_verified, pt.amount_minor_units, pt.currency,
                   pt.payment_status, pt.captured_at, pt.created_at
            FROM payment_transactions pt
            JOIN payment_orders po ON pt.order_id = po.id
            WHERE po.user_id = ?
            ORDER BY pt.created_at DESC
            """,
            (user_id,),
        ) as cursor:
            async for row in cursor:
                txns.append(self._row_to_entity(row))
        return txns

    def _row_to_entity(self, row: tuple) -> PaymentTransaction:
        return PaymentTransaction(
            id=row[0],
            order_id=row[1],
            provider=PaymentProviderType(row[2]),
            provider_payment_id=row[3],
            provider_order_id=row[4],
            provider_signature_verified=bool(row[5]),
            amount_minor_units=row[6],
            currency=row[7],
            payment_status=PaymentTransactionStatus(row[8]),
            captured_at=datetime.fromisoformat(row[9]),
            created_at=datetime.fromisoformat(row[10]),
        )
