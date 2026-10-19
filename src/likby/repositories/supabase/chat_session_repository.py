"""
likby.repositories.supabase.chat_session_repository
Supabase REST implementation of ChatSessionRepository with local caching and fallback.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Optional
from likby.domain.entities.chat_session import ChatSession
from likby.domain.enums import SessionStatus, TerminationReason
from likby.repositories.interfaces import ChatSessionRepository

logger = logging.getLogger(__name__)


class SupabaseChatSessionRepository(ChatSessionRepository):
    """Supabase REST-backed implementation of ChatSessionRepository."""

    def __init__(self, client: Any, local_fallback: Optional[ChatSessionRepository] = None) -> None:
        self._client = client
        self._fallback = local_fallback

    async def get_by_id(self, session_id: str) -> Optional[ChatSession]:
        try:
            res = await asyncio.to_thread(
                self._client.table("chat_sessions").select("*").eq("id", session_id).limit(1).execute
            )
            if res.data:
                session = self._row_to_entity(res.data[0])
                if self._fallback:
                    try:
                        await self._fallback.save(session)
                    except Exception:
                        pass
                return session
        except Exception as exc:
            logger.warning("[SupabaseChatSessionRepository] get_by_id error: %s", exc)

        if self._fallback:
            return await self._fallback.get_by_id(session_id)
        return None

    async def get_active_by_user_id(self, user_id: str) -> Optional[ChatSession]:
        try:
            res = await asyncio.to_thread(
                self._client.table("chat_sessions")
                .select("*")
                .eq("status", "ACTIVE")
                .or_(f"user_a_id.eq.{user_id},user_b_id.eq.{user_id}")
                .order("created_at", desc=True)
                .limit(1)
                .execute
            )
            if res.data:
                session = self._row_to_entity(res.data[0])
                if self._fallback:
                    try:
                        await self._fallback.save(session)
                    except Exception:
                        pass
                return session
        except Exception as exc:
            logger.warning("[SupabaseChatSessionRepository] get_active_by_user_id error: %s", exc)

        if self._fallback:
            return await self._fallback.get_active_by_user_id(user_id)
        return None

    async def save(self, session: ChatSession) -> None:
        if self._fallback:
            try:
                await self._fallback.save(session)
            except Exception as exc:
                logger.warning("[SupabaseChatSessionRepository] local fallback save error: %s", exc)

        meta = {
            "match_score": session.match_score,
            "match_metadata": session.match_metadata,
            "message_count": session.message_count,
            "ended_by_user_id": session.ended_by_user_id,
        }

        payload = {
            "id": session.id,
            "user_a_id": session.user_a_id,
            "user_b_id": session.user_b_id,
            "status": session.status.value if hasattr(session.status, "value") else str(session.status),
            "termination_reason": session.termination_reason.value if session.termination_reason else None,
            "started_at": session.created_at.isoformat() if session.created_at else datetime.now(timezone.utc).isoformat(),
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else datetime.now(timezone.utc).isoformat(),
            "metadata": meta,
            "created_at": session.created_at.isoformat() if session.created_at else datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            await asyncio.to_thread(
                self._client.table("chat_sessions").upsert(payload).execute
            )
        except Exception as exc:
            logger.error("[SupabaseChatSessionRepository] Failed to upsert session %s: %s", session.id, exc)

    def _row_to_entity(self, row: dict) -> ChatSession:
        created_at = datetime.now(timezone.utc)
        if row.get("created_at"):
            created_at = datetime.fromisoformat(row["created_at"])

        last_activity_at = created_at
        if row.get("last_activity_at"):
            last_activity_at = datetime.fromisoformat(row["last_activity_at"])

        ended_at = None
        if row.get("ended_at"):
            ended_at = datetime.fromisoformat(row["ended_at"])

        meta = row.get("metadata") or {}
        term_reason = None
        if row.get("termination_reason"):
            try:
                term_reason = TerminationReason(row["termination_reason"])
            except Exception:
                pass

        return ChatSession(
            id=row["id"],
            user_a_id=row["user_a_id"],
            user_b_id=row["user_b_id"],
            status=SessionStatus(row["status"]),
            match_score=float(meta.get("match_score", 0.0)),
            match_metadata=meta.get("match_metadata", {}),
            message_count=int(meta.get("message_count", 0)),
            created_at=created_at,
            last_activity_at=last_activity_at,
            ended_at=ended_at,
            ended_by_user_id=meta.get("ended_by_user_id"),
            termination_reason=term_reason,
        )
