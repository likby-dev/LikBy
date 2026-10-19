"""
likby.repositories.supabase.user_repository
Supabase REST implementation of UserRepository with local caching and fallback.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Optional
from likby.domain.entities.user import User
from likby.domain.enums import PresenceStatus, UserState, UserStatus
from likby.repositories.interfaces import UserRepository

logger = logging.getLogger(__name__)


class SupabaseUserRepository(UserRepository):
    """Supabase REST-backed implementation of UserRepository."""

    def __init__(self, client: Any, local_fallback: Optional[UserRepository] = None) -> None:
        self._client = client
        self._fallback = local_fallback

    async def get_by_id(self, user_id: str) -> Optional[User]:
        try:
            res = await asyncio.to_thread(
                self._client.table("users").select("*").eq("id", user_id).limit(1).execute
            )
            if res.data:
                user = self._row_to_entity(res.data[0])
                if self._fallback:
                    try:
                        await self._fallback.save(user)
                    except Exception:
                        pass
                return user
        except Exception as exc:
            logger.warning("[SupabaseUserRepository] get_by_id error: %s", exc)

        if self._fallback:
            return await self._fallback.get_by_id(user_id)
        return None

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        try:
            res = await asyncio.to_thread(
                self._client.table("users").select("*").eq("telegram_id", telegram_id).limit(1).execute
            )
            if res.data:
                user = self._row_to_entity(res.data[0])
                if self._fallback:
                    try:
                        await self._fallback.save(user)
                    except Exception:
                        pass
                return user
        except Exception as exc:
            logger.warning("[SupabaseUserRepository] get_by_telegram_id error: %s", exc)

        if self._fallback:
            return await self._fallback.get_by_telegram_id(telegram_id)
        return None

    async def get_by_unique_id(self, unique_id: str) -> Optional[User]:
        clean = unique_id.strip().lstrip("@").lower()
        try:
            res = await asyncio.to_thread(
                self._client.table("users").select("*").ilike("unique_id", clean).limit(1).execute
            )
            if res.data:
                user = self._row_to_entity(res.data[0])
                if self._fallback:
                    try:
                        await self._fallback.save(user)
                    except Exception:
                        pass
                return user
        except Exception as exc:
            logger.warning("[SupabaseUserRepository] get_by_unique_id error: %s", exc)

        if self._fallback:
            return await self._fallback.get_by_unique_id(clean)
        return None

    async def save(self, user: User) -> None:
        # Save to local fallback first for low latency
        if self._fallback:
            try:
                await self._fallback.save(user)
            except Exception as exc:
                logger.warning("[SupabaseUserRepository] local fallback save error: %s", exc)

        # Upsert to Supabase
        unique_handle = user.unique_id if user.unique_id else f"pending_{user.id[-8:]}"
        presence_val = user.presence.value if hasattr(user.presence, "value") else str(user.presence)

        payload = {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "unique_id": unique_handle,
            "state": user.state.value if hasattr(user.state, "value") else str(user.state),
            "status": user.status.value if hasattr(user.status, "value") else str(user.status),
            "age_verified": bool(user.age_verified),
            "terms_accepted_at": user.terms_accepted_at.isoformat() if user.terms_accepted_at else None,
            "karma_score": int(user.karma_score),
            "report_count": int(user.report_count),
            "ban_reason": user.ban_reason,
            "banned_at": user.banned_at.isoformat() if user.banned_at else None,
            "last_active_at": user.last_active_at.isoformat() if user.last_active_at else datetime.now(timezone.utc).isoformat(),
            "created_at": user.created_at.isoformat() if user.created_at else datetime.now(timezone.utc).isoformat(),
            "updated_at": user.updated_at.isoformat() if user.updated_at else datetime.now(timezone.utc).isoformat(),
            "privacy_settings": {
                "presence": presence_val,
                "allow_search": True,
            },
        }

        try:
            await asyncio.to_thread(
                self._client.table("users").upsert(payload).execute
            )
        except Exception as exc:
            logger.error("[SupabaseUserRepository] Failed to upsert user %s to Supabase: %s", user.id, exc)

    def _row_to_entity(self, row: dict) -> User:
        raw_uid = row.get("unique_id")
        unique_id = None if (not raw_uid or raw_uid.startswith("pending_")) else raw_uid

        terms_at = None
        if row.get("terms_accepted_at"):
            terms_at = datetime.fromisoformat(row["terms_accepted_at"])

        banned_at = None
        if row.get("banned_at"):
            banned_at = datetime.fromisoformat(row["banned_at"])

        last_active = datetime.now(timezone.utc)
        if row.get("last_active_at"):
            last_active = datetime.fromisoformat(row["last_active_at"])

        created_at = datetime.now(timezone.utc)
        if row.get("created_at"):
            created_at = datetime.fromisoformat(row["created_at"])

        updated_at = datetime.now(timezone.utc)
        if row.get("updated_at"):
            updated_at = datetime.fromisoformat(row["updated_at"])

        privacy = row.get("privacy_settings") or {}
        presence_str = privacy.get("presence", "ACTIVE")
        try:
            presence = PresenceStatus(presence_str)
        except Exception:
            presence = PresenceStatus.ACTIVE

        return User(
            id=row["id"],
            telegram_id=row["telegram_id"],
            unique_id=unique_id,
            presence=presence,
            state=UserState(row["state"]),
            status=UserStatus(row["status"]),
            age_verified=bool(row.get("age_verified", False)),
            terms_accepted_at=terms_at,
            karma_score=row.get("karma_score", 100),
            report_count=row.get("report_count", 0),
            ban_reason=row.get("ban_reason"),
            banned_at=banned_at,
            last_active_at=last_active,
            created_at=created_at,
            updated_at=updated_at,
        )
