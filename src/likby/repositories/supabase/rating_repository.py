"""
likby.repositories.supabase.rating_repository
Supabase REST implementation of RatingRepository with local fallback.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Optional
from likby.domain.entities.rating import SessionRating
from likby.domain.enums import RatingType
from likby.repositories.interfaces import RatingRepository

logger = logging.getLogger(__name__)


class SupabaseRatingRepository(RatingRepository):
    """Supabase REST-backed implementation of RatingRepository."""

    def __init__(self, client: Any, local_fallback: Optional[RatingRepository] = None) -> None:
        self._client = client
        self._fallback = local_fallback

    async def save(self, rating: SessionRating) -> None:
        if self._fallback:
            try:
                await self._fallback.save(rating)
            except Exception as exc:
                logger.warning("[SupabaseRatingRepository] local fallback save error: %s", exc)

        payload = {
            "id": rating.id,
            "session_id": rating.session_id,
            "rater_user_id": rating.rater_id,
            "rated_user_id": rating.ratee_id,
            "rating_type": rating.rating.value if hasattr(rating.rating, "value") else str(rating.rating),
            "created_at": rating.created_at.isoformat() if rating.created_at else datetime.now(timezone.utc).isoformat(),
        }

        try:
            await asyncio.to_thread(
                self._client.table("ratings").upsert(payload).execute
            )
        except Exception as exc:
            logger.error("[SupabaseRatingRepository] Failed to upsert rating %s: %s", rating.id, exc)

    async def get_by_session_and_rater(self, session_id: str, rater_id: str) -> Optional[SessionRating]:
        try:
            res = await asyncio.to_thread(
                self._client.table("ratings")
                .select("*")
                .eq("session_id", session_id)
                .eq("rater_user_id", rater_id)
                .limit(1)
                .execute
            )
            if res.data:
                return self._row_to_entity(res.data[0])
        except Exception as exc:
            logger.warning("[SupabaseRatingRepository] get_by_session_and_rater error: %s", exc)

        if self._fallback:
            return await self._fallback.get_by_session_and_rater(session_id, rater_id)
        return None

    def _row_to_entity(self, row: dict) -> SessionRating:
        created_at = datetime.now(timezone.utc)
        if row.get("created_at"):
            created_at = datetime.fromisoformat(row["created_at"])
        return SessionRating(
            id=row["id"],
            session_id=row["session_id"],
            rater_id=row["rater_user_id"],
            ratee_id=row["rated_user_id"],
            rating=RatingType(row["rating_type"]),
            created_at=created_at,
        )
