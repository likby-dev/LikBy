"""
likby.repositories.supabase.profile_repository
Supabase REST implementation of ProfileRepository with local caching and fallback.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Optional
from likby.domain.entities.profile import Profile
from likby.domain.enums import Gender, GenderPreference
from likby.repositories.interfaces import ProfileRepository

logger = logging.getLogger(__name__)


class SupabaseProfileRepository(ProfileRepository):
    """Supabase REST-backed implementation of ProfileRepository."""

    def __init__(self, client: Any, local_fallback: Optional[ProfileRepository] = None) -> None:
        self._client = client
        self._fallback = local_fallback

    async def get_by_user_id(self, user_id: str) -> Optional[Profile]:
        try:
            res = await asyncio.to_thread(
                self._client.table("profiles").select("*").eq("user_id", user_id).limit(1).execute
            )
            if res.data:
                profile = self._row_to_entity(res.data[0])
                if self._fallback:
                    try:
                        await self._fallback.save(profile)
                    except Exception:
                        pass
                return profile
        except Exception as exc:
            logger.warning("[SupabaseProfileRepository] get_by_user_id error: %s", exc)

        if self._fallback:
            return await self._fallback.get_by_user_id(user_id)
        return None

    async def get_by_unique_id(self, unique_id: str) -> Optional[Profile]:
        clean = unique_id.strip().lstrip("@").lower()
        try:
            # Query user by unique handle first
            user_res = await asyncio.to_thread(
                self._client.table("users").select("id, unique_id").ilike("unique_id", clean).limit(1).execute
            )
            if user_res.data:
                user_id = user_res.data[0]["id"]
                profile = await self.get_by_user_id(user_id)
                if profile:
                    profile.unique_id = clean
                    return profile
        except Exception as exc:
            logger.warning("[SupabaseProfileRepository] get_by_unique_id error: %s", exc)

        if self._fallback:
            return await self._fallback.get_by_unique_id(clean)
        return None

    async def save(self, profile: Profile) -> None:
        # Save to local fallback first for low latency
        if self._fallback:
            try:
                await self._fallback.save(profile)
            except Exception as exc:
                logger.warning("[SupabaseProfileRepository] local fallback save error: %s", exc)

        gender_val = profile.gender.value if hasattr(profile.gender, "value") else str(profile.gender)
        pref_val = [p.value if hasattr(p, "value") else str(p) for p in profile.preferred_gender_filter]

        payload = {
            "user_id": profile.user_id,
            "display_name": profile.display_name,
            "age": profile.age,
            "gender": gender_val,
            "bio": profile.bio,
            "location_country": profile.location_country,
            "location_city": profile.location_city,
            "languages": profile.languages or ["en"],
            "interests": profile.interests or [],
            "preferred_gender_filter": pref_val,
            "min_age_filter": profile.min_age_filter,
            "max_age_filter": profile.max_age_filter,
            "created_at": profile.created_at.isoformat() if profile.created_at else datetime.now(timezone.utc).isoformat(),
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else datetime.now(timezone.utc).isoformat(),
        }

        try:
            await asyncio.to_thread(
                self._client.table("profiles").upsert(payload).execute
            )
        except Exception as exc:
            logger.error("[SupabaseProfileRepository] Failed to upsert profile for %s: %s", profile.user_id, exc)

    def _row_to_entity(self, row: dict) -> Profile:
        created_at = datetime.now(timezone.utc)
        if row.get("created_at"):
            created_at = datetime.fromisoformat(row["created_at"])

        updated_at = datetime.now(timezone.utc)
        if row.get("updated_at"):
            updated_at = datetime.fromisoformat(row["updated_at"])

        languages = row.get("languages") or ["en"]
        interests = row.get("interests") or []
        raw_prefs = row.get("preferred_gender_filter") or ["ANY"]
        pref_list = []
        for p in raw_prefs:
            try:
                pref_list.append(GenderPreference(p))
            except Exception:
                pref_list.append(GenderPreference.ANY)

        return Profile(
            user_id=row["user_id"],
            unique_id=row.get("unique_id"),
            display_name=row["display_name"],
            age=int(row["age"]),
            gender=Gender(row["gender"]),
            bio=row.get("bio"),
            location_country=row.get("location_country"),
            location_city=row.get("location_city"),
            languages=languages,
            interests=interests,
            preferred_gender_filter=pref_list,
            min_age_filter=int(row.get("min_age_filter", 18)),
            max_age_filter=int(row.get("max_age_filter", 99)),
            created_at=created_at,
            updated_at=updated_at,
        )
