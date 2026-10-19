"""
likby.repositories.supabase.daily_usage_repository
Supabase REST implementation of DailyUsageRepository with local fallback.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Optional
from likby.domain.entities.daily_usage import DailyUsage
from likby.repositories.interfaces import DailyUsageRepository

logger = logging.getLogger(__name__)


class SupabaseDailyUsageRepository(DailyUsageRepository):
    """Supabase REST-backed implementation of DailyUsageRepository."""

    def __init__(self, client: Any, local_fallback: Optional[DailyUsageRepository] = None) -> None:
        self._client = client
        self._fallback = local_fallback

    async def get_or_create(self, user_id: str, usage_date: str) -> DailyUsage:
        if self._fallback:
            try:
                await self._fallback.get_or_create(user_id, usage_date)
            except Exception as exc:
                logger.warning("[SupabaseDailyUsageRepository] local fallback get_or_create error: %s", exc)

        rec_id = f"usg_{user_id}_{usage_date}"
        try:
            res = await asyncio.to_thread(
                self._client.table("daily_usage")
                .select("*")
                .eq("user_id", user_id)
                .eq("usage_date", usage_date)
                .limit(1)
                .execute
            )
            if res.data:
                row = res.data[0]
                return DailyUsage(
                    user_id=row["user_id"],
                    usage_date=str(row["usage_date"]),
                    searches_count=row.get("id_searches_used", 0),
                    requests_count=row.get("connection_requests_used", 0),
                    uploads_count=0,
                    received_count=0,
                )

            # Insert initial record
            payload = {
                "id": rec_id,
                "user_id": user_id,
                "usage_date": usage_date,
                "id_searches_used": 0,
                "connection_requests_used": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await asyncio.to_thread(
                self._client.table("daily_usage").upsert(payload).execute
            )
            return DailyUsage(
                user_id=user_id,
                usage_date=usage_date,
                searches_count=0,
                requests_count=0,
                uploads_count=0,
                received_count=0,
            )
        except Exception as exc:
            logger.warning("[SupabaseDailyUsageRepository] get_or_create error: %s", exc)

        if self._fallback:
            return await self._fallback.get_or_create(user_id, usage_date)
        return DailyUsage(user_id=user_id, usage_date=usage_date)

    async def increment_search(self, user_id: str, usage_date: str) -> int:
        fb_val = 0
        if self._fallback:
            try:
                fb_val = await self._fallback.increment_search(user_id, usage_date)
            except Exception:
                pass

        try:
            current = await self.get_or_create(user_id, usage_date)
            new_count = current.searches_count + 1
            payload = {
                "id": f"usg_{user_id}_{usage_date}",
                "user_id": user_id,
                "usage_date": usage_date,
                "id_searches_used": new_count,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await asyncio.to_thread(
                self._client.table("daily_usage").upsert(payload).execute
            )
            return new_count
        except Exception as exc:
            logger.error("[SupabaseDailyUsageRepository] increment_search error: %s", exc)
            return fb_val or 1

    async def increment_request(self, user_id: str, usage_date: str) -> int:
        fb_val = 0
        if self._fallback:
            try:
                fb_val = await self._fallback.increment_request(user_id, usage_date)
            except Exception:
                pass

        try:
            current = await self.get_or_create(user_id, usage_date)
            new_count = current.requests_count + 1
            payload = {
                "id": f"usg_{user_id}_{usage_date}",
                "user_id": user_id,
                "usage_date": usage_date,
                "connection_requests_used": new_count,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await asyncio.to_thread(
                self._client.table("daily_usage").upsert(payload).execute
            )
            return new_count
        except Exception as exc:
            logger.error("[SupabaseDailyUsageRepository] increment_request error: %s", exc)
            return fb_val or 1

    async def increment_upload(self, user_id: str, usage_date: str) -> int:
        if self._fallback:
            return await self._fallback.increment_upload(user_id, usage_date)
        return 1

    async def increment_received(self, user_id: str, usage_date: str) -> int:
        if self._fallback:
            return await self._fallback.increment_received(user_id, usage_date)
        return 1
