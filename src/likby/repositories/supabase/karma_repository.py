"""
likby.repositories.supabase.karma_repository
Supabase REST implementation of KarmaRepository with local fallback.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, List, Optional
from likby.domain.entities.karma import KarmaLedgerEntry
from likby.domain.enums import KarmaSourceType
from likby.repositories.interfaces import KarmaRepository

logger = logging.getLogger(__name__)


class SupabaseKarmaRepository(KarmaRepository):
    """Supabase REST-backed implementation of KarmaRepository."""

    def __init__(self, client: Any, local_fallback: Optional[KarmaRepository] = None) -> None:
        self._client = client
        self._fallback = local_fallback

    async def save_entry(self, entry: KarmaLedgerEntry) -> bool:
        if self._fallback:
            try:
                saved = await self._fallback.save_entry(entry)
                if not saved:
                    return False
            except Exception as exc:
                logger.warning("[SupabaseKarmaRepository] local fallback save error: %s", exc)

        payload = {
            "id": entry.id,
            "user_id": entry.user_id,
            "delta": entry.delta,
            "reason": entry.source_type.value if hasattr(entry.source_type, "value") else str(entry.source_type),
            "reference_id": entry.reference_id,
            "idempotency_key": entry.idempotency_key,
            "created_at": entry.created_at.isoformat() if entry.created_at else datetime.now(timezone.utc).isoformat(),
        }

        try:
            await asyncio.to_thread(
                self._client.table("karma_ledger").upsert(payload).execute
            )
            return True
        except Exception as exc:
            logger.error("[SupabaseKarmaRepository] Failed to upsert karma ledger %s: %s", entry.id, exc)
            return False

    async def get_user_ledger(self, user_id: str, limit: int = 20) -> List[KarmaLedgerEntry]:
        try:
            res = await asyncio.to_thread(
                self._client.table("karma_ledger")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute
            )
            if res.data:
                return [self._row_to_entity(row) for row in res.data]
        except Exception as exc:
            logger.warning("[SupabaseKarmaRepository] get_user_ledger error: %s", exc)

        if self._fallback:
            return await self._fallback.get_user_ledger(user_id, limit)
        return []

    async def get_user_karma_score(self, user_id: str) -> int:
        if self._fallback:
            return await self._fallback.get_user_karma_score(user_id)
        # Default starting karma is 100
        ledger = await self.get_user_ledger(user_id, limit=500)
        score = 100 + sum(entry.delta for entry in ledger)
        return max(0, min(500, score))

    def _row_to_entity(self, row: dict) -> KarmaLedgerEntry:
        created_at = datetime.now(timezone.utc)
        if row.get("created_at"):
            created_at = datetime.fromisoformat(row["created_at"])

        reason_str = row.get("reason", "SESSION_POSITIVE_RATING")
        try:
            source = KarmaSourceType(reason_str)
        except Exception:
            source = KarmaSourceType.SESSION_POSITIVE_RATING

        return KarmaLedgerEntry(
            id=row["id"],
            user_id=row["user_id"],
            source_type=source,
            reference_id=row.get("reference_id"),
            delta=row["delta"],
            idempotency_key=row["idempotency_key"],
            created_at=created_at,
        )
