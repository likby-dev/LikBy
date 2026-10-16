"""
likby.services.transcript_service
Service for generating standardized human-readable chat transcripts and .txt exports.
"""

from typing import List, Optional
from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.media_asset import MediaAsset
from likby.domain.entities.message import ChatMessage
from likby.domain.enums import MessageType
from likby.repositories.interfaces import (
    ChatSessionRepository,
    MediaAssetRepository,
    MessageRepository,
    UserRepository,
)


class TranscriptFormatter:
    """Formatter that converts structured chat messages into standardized readable text."""

    @classmethod
    def format_session(
        cls,
        session: ChatSession,
        messages: List[ChatMessage],
        user_a_display: str,
        user_b_display: str,
        media_assets_by_id: Optional[dict[str, MediaAsset]] = None,
    ) -> str:
        """Render complete standardized LikBy transcript."""
        started_str = session.started_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        assets = media_assets_by_id or {}

        lines = [
            "LIKBY CHAT SESSION",
            f"Session ID: {session.id}",
            f"Started: {started_str}",
            "",
            "Participants:",
            f"User A (ID: {user_a_display})",
            f"User B (ID: {user_b_display})",
            "",
        ]

        for msg in messages:
            ts_str = msg.created_at.strftime("%H:%M:%S")

            if msg.message_type == MessageType.SYSTEM or msg.sender_id == "SYSTEM":
                lines.append(f"[{ts_str}] SYSTEM: {msg.text or 'Event occurred'}")
                continue

            # Resolve author tag
            if msg.sender_id == session.user_a_id:
                author_tag = f"User A ({user_a_display})"
            elif msg.sender_id == session.user_b_id:
                author_tag = f"User B ({user_b_display})"
            else:
                author_tag = f"{msg.sender_display_id}"

            # Format media reference if present
            if msg.media_asset_id and msg.media_asset_id in assets:
                asset = assets[msg.media_asset_id]
                asset_ref = asset.original_filename or f"{asset.id}.bin"
                caption = f" - {msg.text}" if msg.text else ""
                lines.append(f"[{ts_str}] {author_tag}: [{msg.message_type.value}: {asset.id}_{asset_ref}]{caption}")
            elif msg.media_asset_id:
                caption = f" - {msg.text}" if msg.text else ""
                lines.append(f"[{ts_str}] {author_tag}: [{msg.message_type.value}: {msg.media_asset_id}]{caption}")
            else:
                lines.append(f"[{ts_str}] {author_tag}: {msg.text or ''}")

        lines.extend(["", f"Session Status: {session.status.value}"])
        return "\n".join(lines)


class TranscriptService:
    """Application service for reading and generating chat transcripts."""

    def __init__(
        self,
        session_repo: ChatSessionRepository,
        message_repo: MessageRepository,
        media_repo: MediaAssetRepository,
        user_repo: UserRepository,
    ) -> None:
        self._session_repo = session_repo
        self._message_repo = message_repo
        self._media_repo = media_repo
        self._user_repo = user_repo

    async def get_readable_transcript(self, session_id: str) -> Optional[str]:
        """Fetch session, load ordered messages, and format into readable transcript."""
        session = await self._session_repo.get_by_id(session_id)
        if not session:
            return None

        # Fetch users for stable display IDs
        user_a = await self._user_repo.get_by_id(session.user_a_id)
        user_b = await self._user_repo.get_by_id(session.user_b_id)
        user_a_display = user_a.display_user_id if user_a else session.user_a_id
        user_b_display = user_b.display_user_id if user_b else session.user_b_id

        # Fetch messages in sequence
        messages = await self._message_repo.get_session_messages(session_id, limit=500)

        # Collect media assets
        media_map: dict[str, MediaAsset] = {}
        for m in messages:
            if m.media_asset_id:
                asset = await self._media_repo.get_by_id(m.media_asset_id)
                if asset:
                    media_map[m.media_asset_id] = asset

        return TranscriptFormatter.format_session(
            session=session,
            messages=messages,
            user_a_display=user_a_display,
            user_b_display=user_b_display,
            media_assets_by_id=media_map,
        )

    async def export_transcript_bytes(self, session_id: str) -> Optional[tuple[str, bytes]]:
        """Export session transcript as a downloadable .txt file (filename, bytes)."""
        transcript = await self.get_readable_transcript(session_id)
        if not transcript:
            return None
        filename = f"LikBy_Chat_{session_id}.txt"
        return filename, transcript.encode("utf-8")
