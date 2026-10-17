"""
likby.services.transcript_service
Service for generating standardized, human-readable chat transcripts stored in Google Cloud Firestore.
Adheres strictly to the master format, deterministic chronological ordering, timezone conversion,
and authoritative counter recalculation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import zoneinfo

from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.media_asset import MediaAsset
from likby.domain.entities.message import ChatMessage
from likby.domain.entities.session_event import SessionEvent
from likby.domain.enums import MessageType, SessionStatus
from likby.repositories.interfaces import (
    ChatSessionRepository,
    MediaAssetRepository,
    MessageRepository,
    UserRepository,
)


class TranscriptFormatter:
    """Formatter that converts structured messages and events into the authoritative presentation format."""

    @classmethod
    def format_timestamp(cls, dt: datetime, tz_name: str = "UTC") -> str:
        """Convert UTC datetime to target timezone and format as YYYY-MM-DD HH:mm:ss."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        try:
            target_tz = zoneinfo.ZoneInfo(tz_name)
            local_dt = dt.astimezone(target_tz)
        except Exception:
            local_dt = dt.astimezone(timezone.utc)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def format_session(
        cls,
        session: ChatSession,
        messages: List[ChatMessage],
        user_a_display: str,
        user_b_display: str,
        events: Optional[List[SessionEvent]] = None,
        media_assets_by_id: Optional[Dict[str, MediaAsset]] = None,
        timezone_str: str = "UTC",
    ) -> str:
        """
        Render complete standardized LikBy transcript strictly adhering to the presentation format:

        LIKBY CHAT SESSION
        Session ID: cs_01K8XYZ...

        Participants:
        User A (ID: 100234)
        User B (ID: 100567)

        [2026-10-16 12:30:01] User A (100234): Hi!
        ...
        [2026-10-16 12:30:25] User A (100234): [PHOTO: ast_01K8DEF_photo.jpg]
        ...
        [2026-10-16 12:31:00] SYSTEM: Session reported.

        Session Status: REPORTED
        Total Messages: 6
        Media Attachments: 2
        """
        assets = media_assets_by_id or {}
        raw_events = events or []

        # 1. Header
        lines = [
            "LIKBY CHAT SESSION",
            f"Session ID: {session.id}",
            "",
            "Participants:",
            f"User A (ID: {user_a_display})",
            f"User B (ID: {user_b_display})",
            "",
        ]

        # 2. Merge messages and events in unified chronological timeline
        timeline_items: List[Tuple[datetime, int, str]] = []

        # Track authoritative counters
        total_user_messages = 0
        total_media_attachments = 0

        seen_events = set()

        for msg in messages:
            ts_str = cls.format_timestamp(msg.created_at, timezone_str)

            # Check if message is a SYSTEM event
            if msg.message_type == MessageType.SYSTEM or msg.sender_id == "SYSTEM":
                evt_key = (ts_str, msg.text or "")
                if evt_key not in seen_events:
                    seen_events.add(evt_key)
                    rendered = f"[{ts_str}] SYSTEM: {msg.text or 'Event recorded.'}"
                    timeline_items.append((msg.created_at, msg.sequence, rendered))
                continue

            # Regular user message
            total_user_messages += 1

            # Author label
            if msg.sender_id == session.user_a_id:
                author_tag = f"User A ({user_a_display})"
            elif msg.sender_id == session.user_b_id:
                author_tag = f"User B ({user_b_display})"
            else:
                author_tag = f"User ({msg.sender_display_id or msg.sender_id})"

            # Media attachment or text
            if msg.media_asset_id:
                total_media_attachments += 1
                asset = assets.get(msg.media_asset_id)
                if asset:
                    fname = asset.original_filename or f"{asset.id}.bin"
                    asset_label = f"{asset.id}_{fname}"
                else:
                    asset_label = msg.media_asset_id

                tag_type = msg.message_type.value.upper()
                caption_part = f" - {msg.text}" if msg.text else ""
                rendered = f"[{ts_str}] {author_tag}: [{tag_type}: {asset_label}]{caption_part}"
            else:
                rendered = f"[{ts_str}] {author_tag}: {msg.text or ''}"

            timeline_items.append((msg.created_at, msg.sequence, rendered))

        # Add structured system events
        for ev in raw_events:
            ts_str = cls.format_timestamp(ev.created_at, timezone_str)
            evt_key = (ts_str, ev.display_text)
            if evt_key not in seen_events:
                seen_events.add(evt_key)
                rendered = f"[{ts_str}] SYSTEM: {ev.display_text}"
                timeline_items.append((ev.created_at, ev.sequence, rendered))

        # Sort chronologically by (created_at, sequence)
        timeline_items.sort(key=lambda item: (item[0], item[1]))

        for _, _, rendered_line in timeline_items:
            lines.append(rendered_line)

        # 3. Footer
        status_val = session.status.value if hasattr(session.status, "value") else str(session.status)
        lines.extend([
            "",
            f"Session Status: {status_val}",
            f"Total Messages: {total_user_messages}",
            f"Media Attachments: {total_media_attachments}",
        ])

        return "\n".join(lines)


class TranscriptService:
    """Application service for reading, verifying, exporting, and reconciling chat transcripts."""

    def __init__(
        self,
        session_repo: ChatSessionRepository,
        message_repo: MessageRepository,
        media_repo: MediaAssetRepository,
        user_repo: UserRepository,
        timezone_str: str = "Asia/Kolkata",
    ) -> None:
        self._session_repo = session_repo
        self._message_repo = message_repo
        self._media_repo = media_repo
        self._user_repo = user_repo
        self._timezone_str = timezone_str

    async def get_session_transcript(
        self,
        session_id: str,
        requesting_user_id: Optional[str] = None,
        is_staff: bool = False,
    ) -> Optional[str]:
        """
        Fetch authorized chat session, load chronological messages and events,
        and format into the standardized readable transcript.
        Enforces IDOR / participant access boundary.
        """
        session = await self._session_repo.get_by_id(session_id)
        if not session:
            return None

        # Authorization: Must be participant or authorized staff
        if requesting_user_id and not is_staff:
            if requesting_user_id not in (session.user_a_id, session.user_b_id):
                raise PermissionError("Access denied: You are not an authorized participant in this session.")

        # Load user display labels
        user_a = await self._user_repo.get_by_id(session.user_a_id)
        user_b = await self._user_repo.get_by_id(session.user_b_id)
        user_a_display = (
            user_a.unique_id if user_a and user_a.unique_id else (user_a.display_user_id if user_a else session.user_a_id)
        )
        user_b_display = (
            user_b.unique_id if user_b and user_b.unique_id else (user_b.display_user_id if user_b else session.user_b_id)
        )

        # Load messages and events
        messages = await self._message_repo.get_session_messages(session_id, limit=1000)
        events = []
        if hasattr(self._message_repo, "get_session_events"):
            events = await self._message_repo.get_session_events(session_id, limit=500)

        # Load media asset metadata
        media_map: Dict[str, MediaAsset] = {}
        for m in messages:
            if m.media_asset_id:
                asset = await self._media_repo.get_by_id(m.media_asset_id)
                if asset:
                    media_map[m.media_asset_id] = asset

        return self.render_transcript(
            session=session,
            messages=messages,
            events=events,
            user_a_display=user_a_display,
            user_b_display=user_b_display,
            media_assets_by_id=media_map,
            timezone_str=self._timezone_str,
        )

    def render_transcript(
        self,
        session: ChatSession,
        messages: List[ChatMessage],
        events: Optional[List[SessionEvent]] = None,
        user_a_display: str = "User A",
        user_b_display: str = "User B",
        media_assets_by_id: Optional[Dict[str, MediaAsset]] = None,
        timezone_str: Optional[str] = None,
    ) -> str:
        """Pure synchronous transcript rendering method."""
        tz = timezone_str or self._timezone_str
        return TranscriptFormatter.format_session(
            session=session,
            messages=messages,
            events=events or [],
            user_a_display=user_a_display,
            user_b_display=user_b_display,
            media_assets_by_id=media_assets_by_id or {},
            timezone_str=tz,
        )

    async def get_transcript_summary(
        self,
        session_id: str,
        requesting_user_id: Optional[str] = None,
        is_staff: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve authoritative metadata summary and counters for a chat session."""
        session = await self._session_repo.get_by_id(session_id)
        if not session:
            return None

        if requesting_user_id and not is_staff:
            if requesting_user_id not in (session.user_a_id, session.user_b_id):
                raise PermissionError("Access denied.")

        messages = await self._message_repo.get_session_messages(session_id, limit=1000)
        user_messages = [m for m in messages if m.message_type != MessageType.SYSTEM and m.sender_id != "SYSTEM"]
        media_count = sum(1 for m in user_messages if m.media_asset_id is not None)

        status_val = session.status.value if hasattr(session.status, "value") else str(session.status)

        return {
            "session_id": session.id,
            "status": status_val,
            "participant_ids": [session.user_a_id, session.user_b_id],
            "message_count": len(user_messages),
            "media_attachment_count": media_count,
            "created_at": session.created_at.isoformat(),
            "last_message_at": messages[-1].created_at.isoformat() if messages else session.created_at.isoformat(),
        }

    async def get_paginated_session_history(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        requesting_user_id: Optional[str] = None,
        is_staff: bool = False,
    ) -> Dict[str, Any]:
        """Retrieve paginated chronological messages and events for client rendering."""
        session = await self._session_repo.get_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        if requesting_user_id and not is_staff:
            if requesting_user_id not in (session.user_a_id, session.user_b_id):
                raise PermissionError("Access denied.")

        messages = await self._message_repo.get_session_messages(session_id, limit=limit, offset=offset)
        events = []
        if hasattr(self._message_repo, "get_session_events"):
            events = await self._message_repo.get_session_events(session_id, limit=limit, offset=offset)

        return {
            "session_id": session_id,
            "offset": offset,
            "limit": limit,
            "messages": [
                {
                    "message_id": m.id,
                    "sequence_number": m.sequence,
                    "sender_user_id": m.sender_id,
                    "message_type": m.message_type.value,
                    "text": m.text,
                    "asset_id": m.media_asset_id,
                    "delivery_status": m.delivery_status.value,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
            "events": [
                {
                    "event_id": e.id,
                    "event_type": e.event_type,
                    "display_text": e.display_text,
                    "sequence_number": e.sequence,
                    "created_at": e.created_at.isoformat(),
                }
                for e in events
            ],
        }

    async def rebuild_transcript_projection(self, session_id: str) -> str:
        """
        Re-read all structured messages and events from Firestore,
        reconcile counters, update metadata projection, and return new transcript.
        """
        session = await self._session_repo.get_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        # Recount authoritative counters in Firestore
        if hasattr(self._message_repo, "reconcile_session_counters"):
            await self._message_repo.reconcile_session_counters(session_id)

        return await self.get_session_transcript(session_id) or ""

    async def export_transcript_bytes(
        self, session_id: str, requesting_user_id: Optional[str] = None
    ) -> Optional[Tuple[str, bytes]]:
        """Export session transcript as a downloadable .txt file (filename, bytes)."""
        transcript = await self.get_session_transcript(session_id, requesting_user_id=requesting_user_id)
        if not transcript:
            return None
        filename = f"LikBy_Chat_{session_id}.txt"
        return filename, transcript.encode("utf-8")

    async def get_readable_transcript(self, session_id: str) -> Optional[str]:
        """Backward-compatible alias for get_session_transcript."""
        return await self.get_session_transcript(session_id)
