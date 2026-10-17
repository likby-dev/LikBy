"""
likby.repositories.firestore.message_repository
Firebase Cloud Firestore implementation of MessageRepository.
Authoritative document repository for conversation content and ordered session events.
Topology:
    sessions/{session_id}
    sessions/{session_id}/messages/{message_id}
    sessions/{session_id}/events/{event_id}
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from likby.domain.entities.message import ChatMessage
from likby.domain.enums import MessageDeliveryStatus, MessageType
from likby.repositories.interfaces import MessageRepository


class FirestoreMessageRepository(MessageRepository):
    """
    Firestore repository for chat messages and session events.
    Supports live Google Cloud Firestore SDK and a high-fidelity local memory adapter
    for offline development and hermetic automated testing.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        database_id: str = "(default)",
        credentials_path: Optional[str] = None,
        emulator_host: Optional[str] = None,
        use_mock: bool = False,
    ) -> None:
        self._project_id = project_id
        self._database_id = database_id
        self._credentials_path = credentials_path
        self._emulator_host = emulator_host
        self._client = None
        self._use_mock = use_mock or not project_id

        # High-fidelity mock document store:
        # { session_id: { "messages": { msg_id: dict }, "events": { ev_id: dict }, "last_sequence": int } }
        self._mock_sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

        if not self._use_mock:
            self._init_firestore_client()

    def _init_firestore_client(self) -> None:
        try:
            from google.cloud import firestore  # type: ignore

            if self._emulator_host:
                import os
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
        except Exception as exc:
            # Fallback to local memory mock if SDK client initialization fails
            self._use_mock = True
            self._client = None

    async def get_next_sequence(self, session_id: str) -> int:
        """Atomically increment and return the next per-session sequence number."""
        async with self._lock:
            session_data = self._mock_sessions.setdefault(session_id, {"messages": {}, "events": {}, "last_sequence": 0})
            session_data["last_sequence"] += 1
            seq = session_data["last_sequence"]

        if not self._use_mock and self._client:
            try:
                from google.cloud import firestore  # type: ignore

                session_ref = self._client.collection("sessions").document(session_id)
                await session_ref.set({"last_sequence": firestore.Increment(1)}, merge=True)
                snapshot = await session_ref.get()
                if snapshot.exists:
                    return snapshot.to_dict().get("last_sequence", seq)
            except Exception:
                pass
        return seq

    async def save(self, message: ChatMessage) -> None:
        """Persist message document to sessions/{session_id}/messages/{message_id}."""
        doc_data = {
            "id": message.id,
            "session_id": message.session_id,
            "sender_user_id": message.sender_id,
            "sender_display_id": message.sender_display_id,
            "sequence": message.sequence,
            "message_type": message.message_type.value,
            "text": message.text,
            "media_asset_id": message.media_asset_id,
            "delivery_status": message.delivery_status.value,
            "telegram_msg_id": message.telegram_message_id,
            "created_at": message.created_at.isoformat(),
            "edited_at": None,
            "deleted_at": None,
        }

        async with self._lock:
            session_data = self._mock_sessions.setdefault(message.session_id, {"messages": {}, "events": {}, "last_sequence": 0})
            session_data["messages"][message.id] = doc_data
            if message.sequence > session_data["last_sequence"]:
                session_data["last_sequence"] = message.sequence

        if not self._use_mock and self._client:
            msg_ref = (
                self._client.collection("sessions")
                .document(message.session_id)
                .collection("messages")
                .document(message.id)
            )
            await msg_ref.set(doc_data)

    async def save_event(self, session_id: str, event_id: str, event_type: str, details: Dict[str, Any]) -> None:
        """Persist conversation event to sessions/{session_id}/events/{event_id}."""
        event_data = {
            "id": event_id,
            "session_id": session_id,
            "event_type": event_type,
            "details": details,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        async with self._lock:
            session_data = self._mock_sessions.setdefault(session_id, {"messages": {}, "events": {}, "last_sequence": 0})
            session_data["events"][event_id] = event_data

        if not self._use_mock and self._client:
            ev_ref = (
                self._client.collection("sessions")
                .document(session_id)
                .collection("events")
                .document(event_id)
            )
            await ev_ref.set(event_data)

    async def get_by_id(self, message_id: str) -> Optional[ChatMessage]:
        """Lookup message by identifier across sessions."""
        async with self._lock:
            for s_data in self._mock_sessions.values():
                if message_id in s_data["messages"]:
                    return self._dict_to_entity(s_data["messages"][message_id])

        if not self._use_mock and self._client:
            # Collection group query across all messages
            try:
                query = self._client.collection_group("messages").where("id", "==", message_id).limit(1)
                docs = await query.get()
                if docs:
                    return self._dict_to_entity(docs[0].to_dict())
            except Exception:
                pass
        return None

    async def get_session_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> List[ChatMessage]:
        """Retrieve chronological ordered conversation messages for a session."""
        async with self._lock:
            session_data = self._mock_sessions.get(session_id, {"messages": {}})
            raw_list = list(session_data["messages"].values())
            raw_list.sort(key=lambda m: (m.get("sequence", 0), m.get("created_at", "")))
            slice_items = raw_list[offset : offset + limit]
            entities = [self._dict_to_entity(item) for item in slice_items]

        if not self._use_mock and self._client:
            try:
                coll = (
                    self._client.collection("sessions")
                    .document(session_id)
                    .collection("messages")
                    .order_by("sequence")
                    .offset(offset)
                    .limit(limit)
                )
                docs = await coll.get()
                if docs:
                    return [self._dict_to_entity(d.to_dict()) for d in docs]
            except Exception:
                pass
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
            try:
                query = self._client.collection_group("messages").where("id", "==", message_id).limit(1)
                docs = await query.get()
                if docs:
                    update_payload = {"delivery_status": status.value}
                    if telegram_msg_id is not None:
                        update_payload["telegram_msg_id"] = telegram_msg_id
                    await docs[0].reference.update(update_payload)
            except Exception:
                pass

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

        return ChatMessage(
            id=data["id"],
            session_id=data["session_id"],
            sender_id=data["sender_user_id"],
            sender_display_id=data.get("sender_display_id", data["sender_user_id"]),
            sequence=data.get("sequence", 0),
            message_type=MessageType(data.get("message_type", "TEXT")),
            text=data.get("text"),
            media_asset_id=data.get("media_asset_id"),
            delivery_status=MessageDeliveryStatus(data.get("delivery_status", "DELIVERED")),
            telegram_msg_id=data.get("telegram_msg_id"),
            created_at=dt,
        )
