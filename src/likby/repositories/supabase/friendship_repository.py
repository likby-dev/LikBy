"""
likby.repositories.supabase.friendship_repository
Supabase REST implementation of FriendshipRepository with local fallback.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, List, Optional
from likby.domain.entities.friendship import Friendship
from likby.domain.enums import FriendshipStatus
from likby.repositories.interfaces import FriendshipRepository

logger = logging.getLogger(__name__)


class SupabaseFriendshipRepository(FriendshipRepository):
    """Supabase REST-backed implementation of FriendshipRepository."""

    def __init__(self, client: Any, local_fallback: Optional[FriendshipRepository] = None) -> None:
        self._client = client
        self._fallback = local_fallback

    async def save(self, friendship: Friendship) -> None:
        if self._fallback:
            try:
                await self._fallback.save(friendship)
            except Exception as exc:
                logger.warning("[SupabaseFriendshipRepository] local fallback save error: %s", exc)

        u_low, u_high = sorted([friendship.user_a_id, friendship.user_b_id])
        payload = {
            "id": friendship.id,
            "user_low_id": u_low,
            "user_high_id": u_high,
            "created_at": friendship.created_at.isoformat() if friendship.created_at else datetime.now(timezone.utc).isoformat(),
        }

        try:
            await asyncio.to_thread(
                self._client.table("friendships").upsert(payload).execute
            )
        except Exception as exc:
            logger.error("[SupabaseFriendshipRepository] Failed to upsert friendship %s: %s", friendship.id, exc)

    async def get_by_id(self, friendship_id: str) -> Optional[Friendship]:
        try:
            res = await asyncio.to_thread(
                self._client.table("friendships").select("*").eq("id", friendship_id).limit(1).execute
            )
            if res.data:
                return self._row_to_entity(res.data[0])
        except Exception as exc:
            logger.warning("[SupabaseFriendshipRepository] get_by_id error: %s", exc)

        if self._fallback:
            return await self._fallback.get_by_id(friendship_id)
        return None

    async def get_friendship(self, user_1: str, user_2: str) -> Optional[Friendship]:
        u_low, u_high = sorted([user_1, user_2])
        try:
            res = await asyncio.to_thread(
                self._client.table("friendships")
                .select("*")
                .eq("user_low_id", u_low)
                .eq("user_high_id", u_high)
                .limit(1)
                .execute
            )
            if res.data:
                return self._row_to_entity(res.data[0])
        except Exception as exc:
            logger.warning("[SupabaseFriendshipRepository] get_friendship error: %s", exc)

        if self._fallback:
            return await self._fallback.get_friendship(user_1, user_2)
        return None

    async def get_user_friends(self, user_id: str) -> List[Friendship]:
        try:
            res = await asyncio.to_thread(
                self._client.table("friendships")
                .select("*")
                .or_(f"user_low_id.eq.{user_id},user_high_id.eq.{user_id}")
                .order("created_at", desc=True)
                .execute
            )
            if res.data:
                return [self._row_to_entity(row) for row in res.data]
        except Exception as exc:
            logger.warning("[SupabaseFriendshipRepository] get_user_friends error: %s", exc)

        if self._fallback:
            return await self._fallback.get_user_friends(user_id)
        return []

    async def count_user_friends(self, user_id: str) -> int:
        friends = await self.get_user_friends(user_id)
        return len(friends)

    def _row_to_entity(self, row: dict) -> Friendship:
        created_at = datetime.now(timezone.utc)
        if row.get("created_at"):
            created_at = datetime.fromisoformat(row["created_at"])
        return Friendship(
            id=row["id"],
            user_a_id=row["user_low_id"],
            user_b_id=row["user_high_id"],
            status=FriendshipStatus.ACCEPTED,
            source="session",
            created_at=created_at,
            updated_at=created_at,
        )
