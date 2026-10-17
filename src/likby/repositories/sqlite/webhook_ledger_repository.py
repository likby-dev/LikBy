"""
likby.repositories.sqlite.webhook_ledger_repository
aiosqlite implementation of WebhookLedgerRepository.
"""

from datetime import datetime
from typing import Optional
import aiosqlite
from likby.domain.entities.payment import WebhookEventLedger
from likby.domain.enums import PaymentProviderType, WebhookProcessingStatus
from likby.repositories.interfaces import WebhookLedgerRepository


class SqliteWebhookLedgerRepository(WebhookLedgerRepository):
    """SQLite idempotent deduplication ledger for provider webhooks."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def record_event(self, event: WebhookEventLedger) -> bool:
        """
        Attempts to insert webhook event.
        Returns True if inserted (new event), False if already exists (duplicate event).
        """
        try:
            await self._conn.execute(
                """
                INSERT INTO webhook_event_ledger (
                    id, provider, provider_event_id, event_type,
                    signature_verified, processing_status, payload_hash,
                    received_at, processed_at, safe_error_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.provider.value,
                    event.provider_event_id,
                    event.event_type,
                    1 if event.signature_verified else 0,
                    event.processing_status.value,
                    event.payload_hash,
                    event.received_at.isoformat(),
                    event.processed_at.isoformat(),
                    event.safe_error_code,
                ),
            )
            await self._conn.commit()
            return True
        except aiosqlite.IntegrityError:
            # Duplicate event by provider and provider_event_id
            return False

    async def get_by_provider_event_id(
        self, provider: PaymentProviderType, provider_event_id: str
    ) -> Optional[WebhookEventLedger]:
        async with self._conn.execute(
            "SELECT id, provider, provider_event_id, event_type, signature_verified, processing_status, payload_hash, received_at, processed_at, safe_error_code "
            "FROM webhook_event_ledger WHERE provider = ? AND provider_event_id = ?",
            (provider.value, provider_event_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return WebhookEventLedger(
                id=row[0],
                provider=PaymentProviderType(row[1]),
                provider_event_id=row[2],
                event_type=row[3],
                signature_verified=bool(row[4]),
                processing_status=WebhookProcessingStatus(row[5]),
                payload_hash=row[6],
                received_at=datetime.fromisoformat(row[7]),
                processed_at=datetime.fromisoformat(row[8]),
                safe_error_code=row[9],
            )
