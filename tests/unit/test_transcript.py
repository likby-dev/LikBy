"""
tests.unit.test_transcript
Unit tests for human-readable chat transcript generation and .txt export.
"""

from datetime import datetime, timezone
import pytest

from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.media_asset import MediaAsset
from likby.domain.entities.message import ChatMessage
from likby.domain.enums import ChatSessionStatus, MessageDeliveryStatus, MessageType
from likby.services.transcript_service import TranscriptFormatter


def test_transcript_formatting_specification():
    """Verify transcript adheres strictly to Section 5 specification."""
    session = ChatSession(
        id="cs_01K8XYZ",
        user_a_id="usr_01",
        user_b_id="usr_02",
        status=ChatSessionStatus.ENDED,
        created_at=datetime(2026, 10, 16, 12, 30, 0, tzinfo=timezone.utc),
    )

    messages = [
        ChatMessage(
            id="msg_01",
            session_id=session.id,
            sender_id="usr_01",
            sender_display_id="LK-10001",
            sequence=1,
            message_type=MessageType.TEXT,
            text="Hi!",
            created_at=datetime(2026, 10, 16, 12, 30, 1, tzinfo=timezone.utc),
            delivery_status=MessageDeliveryStatus.DELIVERED,
        ),
        ChatMessage(
            id="msg_02",
            session_id=session.id,
            sender_id="usr_02",
            sender_display_id="LK-10002",
            sequence=2,
            message_type=MessageType.TEXT,
            text="Hello!",
            created_at=datetime(2026, 10, 16, 12, 30, 5, tzinfo=timezone.utc),
            delivery_status=MessageDeliveryStatus.DELIVERED,
        ),
        ChatMessage(
            id="msg_03",
            session_id=session.id,
            sender_id="usr_01",
            sender_display_id="LK-10001",
            sequence=3,
            message_type=MessageType.PHOTO,
            media_asset_id="ast_01K8DEF",
            text=None,
            created_at=datetime(2026, 10, 16, 12, 30, 25, tzinfo=timezone.utc),
            delivery_status=MessageDeliveryStatus.DELIVERED,
        ),
        ChatMessage(
            id="msg_04",
            session_id=session.id,
            sender_id="SYSTEM",
            sender_display_id="SYSTEM",
            sequence=4,
            message_type=MessageType.SYSTEM,
            text="Session reported.",
            created_at=datetime(2026, 10, 16, 12, 31, 0, tzinfo=timezone.utc),
            delivery_status=MessageDeliveryStatus.DELIVERED,
        ),
    ]

    media_map = {
        "ast_01K8DEF": MediaAsset(
            id="ast_01K8DEF",
            session_id=session.id,
            message_id="msg_03",
            bucket="likby-media",
            object_key="likby/prod/2026/10/cs_01K8XYZ/msg_03/ast_01K8DEF_photo.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            original_filename="photo.jpg",
        )
    }

    transcript = TranscriptFormatter.format_session(
        session=session,
        messages=messages,
        user_a_display="LK-10001",
        user_b_display="LK-10002",
        media_assets_by_id=media_map,
    )

    # 1. Header checks
    assert "LIKBY CHAT SESSION" in transcript
    assert "Session ID: cs_01K8XYZ" in transcript
    assert "Started: 2026-10-16 12:30:00 UTC" in transcript
    assert "User A (ID: LK-10001)" in transcript
    assert "User B (ID: LK-10002)" in transcript

    # 2. Chronological message lines
    assert "[12:30:01] User A (LK-10001): Hi!" in transcript
    assert "[12:30:05] User B (LK-10002): Hello!" in transcript
    assert "[12:30:25] User A (LK-10001): [PHOTO: ast_01K8DEF_photo.jpg]" in transcript
    assert "[12:31:00] SYSTEM: Session reported." in transcript

    # 3. Footer check
    assert "Session Status: ENDED" in transcript
