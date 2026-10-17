"""
likby.repositories.firestore.message_repository
Firebase Cloud Firestore implementation of MessageRepository.
Authoritative document repository for conversation content, structured system events, and transcripts.

Topology:
    chat_sessions/{session_id}
    chat_sessions/{session_id}/messages/{message_id}
    chat_sessions/{session_id}/events/{event_id}
"""

import asyncio
import logging
import os
import random
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from likby.domain.entities.message import ChatMessage
from likby.domain.entities.session_event import SessionEvent
from likby.domain.enums import MessageDeliveryStatus, MessageType
from likby.repositories.interfaces import MessageRepository

logger = logging.getLogger("likby.firestore")


class FirestoreMessageRepository(MessageRepository):
    """
    Firestore repository for chat messages, structured events, and session metadata.
    Supports live Google Cloud Firestore AsyncClient with automatic exponential backoff retries,
    idempotent writes, and a high-fidelity local memory adapter for testing and offline development.
    """

    PRIMARY_COLLECTION = "chat_sessions"
    LEGACY_ALIAS_COLLECTION = "sessions"

    def __init__(
        self,
        project_id: Optional[str] = None,
        database_id: str = "(default)",
        credentials_path: Optional[str] = None,
        emulator_host: Optional[str] = None,
        use_mock: bool = False,
        max_attempts: int = 5,
        retry_base_seconds: float = 1.0,
        retry_max_seconds: float = 30.0,
    ) -> None:
        self._project_id = project_id
        self._database_id = database_id
        self._credentials_path = credentials_path
        self._emulator_host = emulator_host
        self._max_attempts = max_attempts
        self._retry_base_seconds = retry_base_seconds
        self._retry_max_seconds = retry_max_seconds
        self._client = None
        self._use_mock = use_mock or not project_id

        # High-fidelity mock document store:
        # { session_id: { "metadata": dict, "messages": { msg_id: dict }, "events": { ev_id: dict }, "last_sequence": int } }
        self._mock_sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

        if not self._use_mock:
            self._init_firestore_client()

    def _init_firestore_client(self) -> None:
        try:
            from google.cloud import firestore  # type: ignore

            if self._emulator_host:
                os.environ["FIRESTORE_EMULATOR_HOST"] = self._emulator_host

            if self._credentials_path and os.path.exists(self._credentials_path):
                from google.oauth2 import service_account

                creds = service_account.Credentials.from_service_account_file(self._credentials_path)
                self._client = firestore.AsyncClient(
                    project=self._project_id,
                    database=self._database_id,
                    credentials=creds,
                )
            else:
                self._client = firestore.AsyncClient(
                    project=self._project_id,
                    database=self._database_id,
                )
            logger.info("Initialized Cloud Firestore AsyncClient for project %s", self._project_id)
        except Exception as exc:
            logger.warning("Firestore client initialization failed (%s); falling back to in-memory mock", exc)
            self._use_mock = True
            self._client = None

    async def _execute_with_retry(self, operation: Callable[..., Any], op_name: str) -> Any:
        """Execute Firestore async call with exponential backoff and jitter."""
        attempt = 0
        while True:
            attempt += 1
            try:
                return await operation()
            except Exception as exc:
                if attempt >= self._max_attempts:
                    logger.error("Firestore operation '%s' permanently failed after %d attempts: %s", op_name, attempt, exc)
                    raise
                delay = min(self._retry_max_seconds, self._retry_base_seconds * (2 ** (attempt - 1)))
                jitter = random.uniform(0.0, 0.5 * delay)
                wait_time = delay + jitter
                logger.warning("Firestore operation '%s' transient error (%s). Retrying in %.2fs (attempt %d/%d)", op_name, exc, wait_time, attempt, self._max_attempts)
                await asyncio.sleep(wait_time)

    async def get_next_sequence(self, session_id: str) -> int:
        """Atomically increment and return the next authoritative per-session sequence number."""
        async with self._lock:
            session_data = self._mock_sessions.setdefault(
                session_id, {"metadata": {}, "messages": {}, "events": {}, "last_sequence": 0}
            )
            session_data["last_sequence"] += 1
            seq = session_data["last_sequence"]

        if not self._use_mock and self._client:
            try:
                from google.cloud import firestore  # type: ignore

                async def _op():
                    doc_ref = self._client.collection(self.PRIMARY_COLLECTION).document(session_id)
                    await doc_ref.set({"last_sequence": firestore.Increment(1)}, merge=True)
                    snap = await doc_ref.get()
                    if snap.exists:
                        return snap.to_dict().get("last_sequence", seq)
                    return seq

                return await self._execute_with_retry(_op, f"get_next_sequence:{session_id}")
            except Exception as exc:
                logger.warning("Falling back to local sequence for %s: %s", session_id, exc)
        return seq

    async def save(
        self,
        message: ChatMessage,
        asset_name: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> None:
        """
        Persist message document idempotently to:
        chat_sessions/{session_id}/messages/{message_id}
        """
        now_iso = message.created_at.isoformat() if message.created_at else datetime.now(timezone.utc).isoformat()
        resolved_key = idempotency_key or f"{message.session_id}_{message.sequence}_{message.id}"

        doc_data = {
            "id": message.id,
            "message_id": message.id,
            "session_id": message.session_id,
            "sequence": message.sequence,
            "sequence_number": message.sequence,
            "sender_user_id": message.sender_id,
            "sender_display_id": message.sender_display_id,
            "message_type": message.message_type.value,
            "text": message.text,
            "asset_id": message.media_asset_id,
            "media_asset_id": message.media_asset_id,
            "asset_name": asset_name,
            "delivery_status": message.delivery_status.value,
            "telegram_msg_id": message.telegram_message_id,
            "idempotency_key": resolved_key,
            "created_at": now_iso,
            "edited_at": None,
            "deleted_at": None,
        }

        async with self._lock:
            s_data = self._mock_sessions.setdefault(
                message.session_id, {"metadata": {}, "messages": {}, "events": {}, "last_sequence": 0}
            )
            s_data["messages"][message.id] = doc_data
            if message.sequence > s_data["last_sequence"]:
                s_data["last_sequence"] = message.sequence

            # Update session summary metadata
            meta = s_data.setdefault("metadata", {
                "session_id": message.session_id,
                "status": "ACTIVE",
                "message_count": 0,
                "media_attachment_count": 0,
                "created_at": now_iso,
                "transcript_version": 1,
            })
            meta["last_message_at"] = now_iso
            meta["transcript_updated_at"] = now_iso
            meta["message_count"] = len(s_data["messages"])
            meta["media_attachment_count"] = sum(
                1 for m in s_data["messages"].values() if m.get("asset_id") or m.get("media_asset_id")
            )

        if not self._use_mock and self._client:
            async def _op():
                # Write to primary collection chat_sessions/{session_id}/messages/{message_id}
                msg_ref = (
                    self._client.collection(self.PRIMARY_COLLECTION)
                    .document(message.session_id)
                    .collection("messages")
                    .document(message.id)
                )
                await msg_ref.set(doc_data, merge=True)

                # Keep session metadata document updated
                sess_ref = self._client.collection(self.PRIMARY_COLLECTION).document(message.session_id)
                await sess_ref.set(
                    {
                        "session_id": message.session_id,
                        "last_message_at": now_iso,
                        "transcript_updated_at": now_iso,
                        "transcript_version": 1,
                    },
                    merge=True,
                )

            await self._execute_with_retry(_op, f"save_message:{message.id}")

    async def save_event(
        self,
        session_id: str,
        event_id: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        display_text: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        sequence: Optional[int] = None,
    ) -> SessionEvent:
        """
        Persist structured system event idempotently to:
        chat_sessions/{session_id}/events/{event_id}
        """
        now_dt = datetime.now(timezone.utc)
        payload = details or {}
        resolved_display = display_text or payload.get("display_text") or f"System event: {event_type}"
        seq = sequence or 0

        event_data = {
            "id": event_id,
            "event_id": event_id,
            "session_id": session_id,
            "event_type": event_type,
            "actor_user_id": actor_user_id,
            "display_text": resolved_display,
            "sequence": seq,
            "sequence_number": seq,
            "details": payload,
            "metadata": payload,
            "created_at": now_dt.isoformat(),
        }

        async with self._lock:
            s_data = self._mock_sessions.setdefault(
                session_id, {"metadata": {}, "messages": {}, "events": {}, "last_sequence": 0}
            )
            s_data["events"][event_id] = event_data

        if not self._use_mock and self._client:
            async def _op():
                ev_ref = (
                    self._client.collection(self.PRIMARY_COLLECTION)
                    .document(session_id)
                    .collection("events")
                    .document(event_id)
                )
                await ev_ref.set(event_data, merge=True)

            await self._execute_with_retry(_op, f"save_event:{event_id}")

        return SessionEvent(
            id=event_id,
            session_id=session_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            display_text=resolved_display,
            sequence=seq,
            metadata=payload,
            created_at=now_dt,
        )

    async def save_session_metadata(
        self,
        session_id: str,
        participant_ids: List[str],
        status: str,
        message_count: Optional[int] = None,
        media_attachment_count: Optional[int] = None,
    ) -> None:
        """Persist or update chat session metadata document in Firestore."""
        now_iso = datetime.now(timezone.utc).isoformat()
        meta_data: Dict[str, Any] = {
            "session_id": session_id,
            "participant_ids": participant_ids,
            "participants": participant_ids,  # legacy compatibility
            "status": status,
            "transcript_version": 1,
            "transcript_updated_at": now_iso,
        }
        if message_count is not None:
            meta_data["message_count"] = message_count
        if media_attachment_count is not None:
            meta_data["media_attachment_count"] = media_attachment_count

        async with self._lock:
            s_data = self._mock_sessions.setdefault(
                session_id, {"metadata": {}, "messages": {}, "events": {}, "last_sequence": 0}
            )
            s_data["metadata"].update(meta_data)

        if not self._use_mock and self._client:
            async def _op():
                sess_ref = self._client.collection(self.PRIMARY_COLLECTION).document(session_id)
                await sess_ref.set(meta_data, merge=True)

            await self._execute_with_retry(_op, f"save_metadata:{session_id}")

    async def get_session_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve chat session metadata document."""
        async with self._lock:
            s_data = self._mock_sessions.get(session_id)
            if s_data and s_data.get("metadata"):
                return dict(s_data["metadata"])

        if not self._use_mock and self._client:
            try:
                snap = await self._client.collection(self.PRIMARY_COLLECTION).document(session_id).get()
                if snap.exists:
                    return snap.to_dict()
                # Check legacy collection
                snap_leg = await self._client.collection(self.LEGACY_ALIAS_COLLECTION).document(session_id).get()
                if snap_leg.exists:
                    return snap_leg.to_dict()
            except Exception as exc:
                logger.warning("Error loading session metadata for %s: %s", session_id, exc)
        return None

    async def get_by_id(self, message_id: str) -> Optional[ChatMessage]:
        """Lookup message by identifier across all sessions."""
        async with self._lock:
            for s_data in self._mock_sessions.values():
                if message_id in s_data["messages"]:
                    return self._dict_to_entity(s_data["messages"][message_id])

        if not self._use_mock and self._client:
            try:
                query = self._client.collection_group("messages").where("id", "==", message_id).limit(1)
                docs = await query.get()
                if docs:
                    return self._dict_to_entity(docs[0].to_dict())
            except Exception as exc:
                logger.warning("Error fetching message by id %s: %s", message_id, exc)
        return None

    async def get_session_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> List[ChatMessage]:
        """Retrieve chronologically ordered conversation messages for a session."""
        async with self._lock:
            s_data = self._mock_sessions.get(session_id, {"messages": {}})
            raw_list = list(s_data["messages"].values())
            raw_list.sort(key=lambda m: (m.get("sequence", 0), m.get("sequence_number", 0), m.get("created_at", "")))
            slice_items = raw_list[offset : offset + limit]
            entities = [self._dict_to_entity(item) for item in slice_items]

        if not self._use_mock and self._client:
            try:
                coll = (
                    self._client.collection(self.PRIMARY_COLLECTION)
                    .document(session_id)
                    .collection("messages")
                    .order_by("sequence")
                    .offset(offset)
                    .limit(limit)
                )
                docs = await coll.get()
                if not docs:
                    # Fallback to legacy path if empty
                    coll_leg = (
                        self._client.collection(self.LEGACY_ALIAS_COLLECTION)
                        .document(session_id)
                        .collection("messages")
                        .order_by("sequence")
                        .offset(offset)
                        .limit(limit)
                    )
                    docs = await coll_leg.get()

                if docs:
                    return [self._dict_to_entity(d.to_dict()) for d in docs]
            except Exception as exc:
                logger.warning("Error fetching session messages for %s: %s", session_id, exc)
        return entities

    async def get_session_events(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> List[SessionEvent]:
        """Retrieve chronologically ordered system events for a session."""
        async with self._lock:
            s_data = self._mock_sessions.get(session_id, {"events": {}})
            raw_list = list(s_data["events"].values())
            raw_list.sort(key=lambda e: (e.get("created_at", ""), e.get("sequence", 0)))
            slice_items = raw_list[offset : offset + limit]
            entities = [self._dict_to_event_entity(item) for item in slice_items]

        if not self._use_mock and self._client:
            try:
                coll = (
                    self._client.collection(self.PRIMARY_COLLECTION)
                    .document(session_id)
                    .collection("events")
                    .order_by("created_at")
                    .offset(offset)
                    .limit(limit)
                )
                docs = await coll.get()
                if docs:
                    return [self._dict_to_event_entity(d.to_dict()) for d in docs]
            except Exception as exc:
                logger.warning("Error fetching session events for %s: %s", session_id, exc)
        return entities

    async def update_delivery_status(
        self,
        message_id: str,
        status: MessageDeliveryStatus,
        telegram_msg_id: Optional[int] = None,
    ) -> None:
        """Update delivery outcome for message document."""
        async with self._lock:
            for s_data in self._mock_sessions.values():
                if message_id in s_data["messages"]:
                    msg_dict = s_data["messages"][message_id]
                    msg_dict["delivery_status"] = status.value
                    if telegram_msg_id is not None:
                        msg_dict["telegram_msg_id"] = telegram_msg_id

        if not self._use_mock and self._client:
            async def _op():
                query = self._client.collection_group("messages").where("id", "==", message_id).limit(1)
                docs = await query.get()
                if docs:
                    update_payload: Dict[str, Any] = {"delivery_status": status.value}
                    if telegram_msg_id is not None:
                        update_payload["telegram_msg_id"] = telegram_msg_id
                    await docs[0].reference.update(update_payload)

            await self._execute_with_retry(_op, f"update_delivery_status:{message_id}")

    async def reconcile_session_counters(self, session_id: str) -> Tuple[int, int]:
        """
        Authoritative recount of message count and media attachment count from individual records.
        Guarantees that retries never cause counter drift or false increments.
        """
        messages = await self.get_session_messages(session_id, limit=1000)
        # Exclude SYSTEM events if stored as messages
        user_messages = [m for m in messages if m.message_type != MessageType.SYSTEM and m.sender_id != "SYSTEM"]
        total_messages = len(user_messages)
        media_count = sum(1 for m in user_messages if m.media_asset_id is not None)

        async with self._lock:
            s_data = self._mock_sessions.setdefault(
                session_id, {"metadata": {}, "messages": {}, "events": {}, "last_sequence": 0}
            )
            meta = s_data.setdefault("metadata", {})
            meta["message_count"] = total_messages
            meta["media_attachment_count"] = media_count

        if not self._use_mock and self._client:
            async def _op():
                doc_ref = self._client.collection(self.PRIMARY_COLLECTION).document(session_id)
                await doc_ref.set(
                    {
                        "message_count": total_messages,
                        "media_attachment_count": media_count,
                        "transcript_updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    merge=True,
                )

            await self._execute_with_retry(_op, f"reconcile_counters:{session_id}")

        return total_messages, media_count

    def _dict_to_entity(self, data: Dict[str, Any]) -> ChatMessage:
        raw_dt = data.get("created_at")
        if isinstance(raw_dt, str):
            try:
                dt = datetime.fromisoformat(raw_dt)
            except Exception:
                dt = datetime.now(timezone.utc)
        elif isinstance(raw_dt, datetime):
            dt = raw_dt
        else:
            dt = datetime.now(timezone.utc)

        seq = data.get("sequence_number") or data.get("sequence", 0)
        msg_id = data.get("message_id") or data.get("id", "")
        asset_id = data.get("asset_id") or data.get("media_asset_id")

        return ChatMessage(
            id=msg_id,
            session_id=data.get("session_id", ""),
            sender_id=data.get("sender_user_id", ""),
            sender_display_id=data.get("sender_display_id", data.get("sender_user_id", "")),
            sequence=seq,
            message_type=MessageType(data.get("message_type", "TEXT")),
            text=data.get("text"),
            media_asset_id=asset_id,
            delivery_status=MessageDeliveryStatus(data.get("delivery_status", "DELIVERED")),
            telegram_msg_id=data.get("telegram_msg_id"),
            created_at=dt,
        )

    def _dict_to_event_entity(self, data: Dict[str, Any]) -> SessionEvent:
        raw_dt = data.get("created_at")
        if isinstance(raw_dt, str):
            try:
                dt = datetime.fromisoformat(raw_dt)
            except Exception:
                dt = datetime.now(timezone.utc)
        elif isinstance(raw_dt, datetime):
            dt = raw_dt
        else:
            dt = datetime.now(timezone.utc)

        ev_id = data.get("event_id") or data.get("id", "")
        seq = data.get("sequence_number") or data.get("sequence", 0)
        display = data.get("display_text") or (data.get("details") or {}).get("display_text") or data.get("event_type", "System Event")

        return SessionEvent(
            id=ev_id,
            session_id=data.get("session_id", ""),
            event_type=data.get("event_type", ""),
            actor_user_id=data.get("actor_user_id"),
            display_text=display,
            sequence=seq,
            metadata=data.get("metadata") or data.get("details") or {},
            created_at=dt,
        )
