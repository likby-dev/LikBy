"""
likby.repositories.supabase.like_repository
Supabase REST implementation of LikeRepository with local fallback.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, List, Optional
from likby.domain.entities.like import Like
from likby.repositories.interfaces import LikeRepository

logger = logging.getLogger(__name__)


class SupabaseLikeRepository(LikeRepository):
    """Supabase REST-backed implementation of LikeRepository."""

    def __init__(self, client: Any, local_fallback: Optional[LikeRepository] = None) -> None:
        self._client = client
        self._fallback = local_fallback

    async def save(self, like: Like) -> None:
        if self._fallback:
            try:
                await self._fallback.save(like)
            except Exception as exc:
                logger.warning("[SupabaseLikeRepository] local fallback save error: %s", exc)

        payload = {
            "id": like.id,
            "sender_id": like.sender_id,
            "target_id": like.target_id,
            "session_id": like.session_id,
            "created_at": like.created_at.isoformat() if like.created_at else datetime.now(timezone.utc).isoformat(),
        }

        try:
            await asyncio.to_thread(
                self._client.table("likes").upsert(payload).execute
            )
        except Exception as exc:
            logger.error("[SupabaseLikeRepository] Failed to upsert like %s: %s", like.id, exc)

    async def get_like(self, sender_id: str, target_id: str) -> Optional[Like]:
        try:
            res = await asyncio.to_thread(
                self._client.table("likes")
                .select("*")
                .eq("sender_id", sender_id)
                .eq("target_id", target_id)
                .limit(1)
                .execute
            )
            if res.data:
                return self._row_to_entity(res.data[0])
        except Exception as exc:
            logger.warning("[SupabaseLikeRepository] get_like error: %s", exc)

        if self._fallback:
            return await self._fallback.get_like(sender_id, target_id)
        return None

    async def get_incoming_likes(self, target_id: str) -> List[Like]:
        try:
            res = await asyncio.to_thread(
                self._client.table("likes")
                .select("*")
                .eq("target_id", target_id)
                .order("created_at", desc=True)
                .execute
            )
            if res.data:
                return [self._row_to_entity(row) for row in res.data]
        except Exception as exc:
            logger.warning("[SupabaseLikeRepository] get_incoming_likes error: %s", exc)

        if self._fallback:
            return await self._fallback.get_incoming_likes(target_id)
        return []

    def _row_to_entity(self, row: dict) -> Like:
        created_at = datetime.now(timezone.utc)
        if row.get("created_at"):
            created_at = datetime.fromisoformat(row["created_at"])
        return Like(
            id=row["id"],
            sender_id=row["sender_id"],
            target_id=row["target_id"],
            session_id=row.get("session_id"),
            is_active=True,
            created_at=created_at,
        )
