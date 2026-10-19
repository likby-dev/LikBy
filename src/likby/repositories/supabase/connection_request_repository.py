"""
likby.repositories.supabase.connection_request_repository
Supabase REST implementation of ConnectionRequestRepository with local fallback.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, List, Optional
from likby.domain.entities.connection_request import ConnectionRequest
from likby.domain.enums import ConnectionRequestStatus
from likby.repositories.interfaces import ConnectionRequestRepository

logger = logging.getLogger(__name__)


class SupabaseConnectionRequestRepository(ConnectionRequestRepository):
    """Supabase REST-backed implementation of ConnectionRequestRepository."""

    def __init__(self, client: Any, local_fallback: Optional[ConnectionRequestRepository] = None) -> None:
        self._client = client
        self._fallback = local_fallback

    async def save(self, request: ConnectionRequest) -> None:
        if self._fallback:
            try:
                await self._fallback.save(request)
            except Exception as exc:
                logger.warning("[SupabaseConnectionRequestRepository] local fallback save error: %s", exc)

        payload = {
            "id": request.id,
            "requester_id": request.sender_id,
            "target_id": request.target_id,
            "status": request.status.value if hasattr(request.status, "value") else str(request.status),
            "created_at": request.created_at.isoformat() if request.created_at else datetime.now(timezone.utc).isoformat(),
            "responded_at": request.resolved_at.isoformat() if request.resolved_at else None,
        }

        try:
            await asyncio.to_thread(
                self._client.table("connection_requests").upsert(payload).execute
            )
        except Exception as exc:
            logger.error("[SupabaseConnectionRequestRepository] Failed to upsert request %s: %s", request.id, exc)

    async def get_by_id(self, request_id: str) -> Optional[ConnectionRequest]:
        try:
            res = await asyncio.to_thread(
                self._client.table("connection_requests").select("*").eq("id", request_id).limit(1).execute
            )
            if res.data:
                return self._row_to_entity(res.data[0])
        except Exception as exc:
            logger.warning("[SupabaseConnectionRequestRepository] get_by_id error: %s", exc)

        if self._fallback:
            return await self._fallback.get_by_id(request_id)
        return None

    async def get_pending_between(self, sender_id: str, target_id: str) -> Optional[ConnectionRequest]:
        try:
            res = await asyncio.to_thread(
                self._client.table("connection_requests")
                .select("*")
                .eq("requester_id", sender_id)
                .eq("target_id", target_id)
                .eq("status", "PENDING")
                .limit(1)
                .execute
            )
            if res.data:
                return self._row_to_entity(res.data[0])
        except Exception as exc:
            logger.warning("[SupabaseConnectionRequestRepository] get_pending_between error: %s", exc)

        if self._fallback:
            return await self._fallback.get_pending_between(sender_id, target_id)
        return None

    async def get_incoming_requests(self, target_id: str) -> List[ConnectionRequest]:
        try:
            res = await asyncio.to_thread(
                self._client.table("connection_requests")
                .select("*")
                .eq("target_id", target_id)
                .eq("status", "PENDING")
                .order("created_at", desc=True)
                .execute
            )
            if res.data:
                return [self._row_to_entity(row) for row in res.data]
        except Exception as exc:
            logger.warning("[SupabaseConnectionRequestRepository] get_incoming_requests error: %s", exc)

        if self._fallback:
            return await self._fallback.get_incoming_requests(target_id)
        return []

    def _row_to_entity(self, row: dict) -> ConnectionRequest:
        created_at = datetime.now(timezone.utc)
        if row.get("created_at"):
            created_at = datetime.fromisoformat(row["created_at"])
        resolved_at = None
        if row.get("responded_at"):
            resolved_at = datetime.fromisoformat(row["responded_at"])

        return ConnectionRequest(
            id=row["id"],
            sender_id=row["requester_id"],
            target_id=row["target_id"],
            status=ConnectionRequestStatus(row["status"]),
            created_at=created_at,
            resolved_at=resolved_at,
        )
