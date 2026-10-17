"""
tests.unit.test_transcript
Unit tests for human-readable chat transcript generation, timezone conversion,
media placeholders, and authoritative counter calculation.
"""

from datetime import datetime, timezone
import pytest

from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.media_asset import MediaAsset
from likby.domain.entities.message import ChatMessage
from likby.domain.entities.session_event import SessionEvent
from likby.domain.enums import ChatSessionStatus, MessageDeliveryStatus, MessageType, SessionStatus
from likby.services.transcript_service import TranscriptFormatter


def test_transcript_formatting_specification():
    """Verify transcript adheres strictly to the required Master Prompt specification."""
    session = ChatSession(
        id="cs_01K8XYZ",
        user_a_id="usr_01",
        user_b_id="usr_02",
        status=SessionStatus.REPORTED,
        created_at=datetime(2026, 10, 16, 12, 30, 0, tzinfo=timezone.utc),
    )

    messages = [
        ChatMessage(
            id="msg_01",
            session_id=session.id,
            sender_id="usr_01",
            sender_display_id="100234",
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
            sender_display_id="100567",
            sequence=2,
            message_type=MessageType.TEXT,
            text="Hello 😊",
            created_at=datetime(2026, 10, 16, 12, 30, 5, tzinfo=timezone.utc),
            delivery_status=MessageDeliveryStatus.DELIVERED,
        ),
        ChatMessage(
            id="msg_03",
            session_id=session.id,
            sender_id="usr_01",
            sender_display_id="100234",
            sequence=3,
            message_type=MessageType.TEXT,
            text="How was your day?",
            created_at=datetime(2026, 10, 16, 12, 30, 12, tzinfo=timezone.utc),
            delivery_status=MessageDeliveryStatus.DELIVERED,
        ),
        ChatMessage(
            id="msg_04",
            session_id=session.id,
            sender_id="usr_02",
            sender_display_id="100567",
            sequence=4,
            message_type=MessageType.TEXT,
            text="It was great!",
            created_at=datetime(2026, 10, 16, 12, 30, 20, tzinfo=timezone.utc),
            delivery_status=MessageDeliveryStatus.DELIVERED,
        ),
        ChatMessage(
            id="msg_05",
            session_id=session.id,
            sender_id="usr_01",
            sender_display_id="100234",
            sequence=5,
            message_type=MessageType.PHOTO,
            media_asset_id="ast_01K8DEF",
            text=None,
            created_at=datetime(2026, 10, 16, 12, 30, 25, tzinfo=timezone.utc),
            delivery_status=MessageDeliveryStatus.DELIVERED,
        ),
        ChatMessage(
            id="msg_06",
            session_id=session.id,
            sender_id="usr_02",
            sender_display_id="100567",
            sequence=6,
            message_type=MessageType.VIDEO,
            media_asset_id="ast_01K8JKL",
            text=None,
            created_at=datetime(2026, 10, 16, 12, 30, 30, tzinfo=timezone.utc),
            delivery_status=MessageDeliveryStatus.DELIVERED,
        ),
    ]

    events = [
        SessionEvent(
            id="evt_01",
            session_id=session.id,
            event_type="SESSION_REPORTED",
            display_text="Session reported.",
            sequence=7,
            created_at=datetime(2026, 10, 16, 12, 31, 0, tzinfo=timezone.utc),
        ),
        SessionEvent(
            id="evt_02",
            session_id=session.id,
            event_type="REPORT_SUBMITTED",
            display_text="Report submitted for review.",
            sequence=8,
            created_at=datetime(2026, 10, 16, 12, 31, 5, tzinfo=timezone.utc),
        ),
    ]

    media_map = {
        "ast_01K8DEF": MediaAsset(
            id="ast_01K8DEF",
            session_id=session.id,
            message_id="msg_05",
            bucket="likby-media",
            object_key="likby/prod/2026/10/cs_01K8XYZ/msg_05/ast_01K8DEF_photo.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            original_filename="photo.jpg",
        ),
        "ast_01K8JKL": MediaAsset(
            id="ast_01K8JKL",
            session_id=session.id,
            message_id="msg_06",
            bucket="likby-media",
            object_key="likby/prod/2026/10/cs_01K8XYZ/msg_06/ast_01K8JKL_video.mp4",
            mime_type="video/mp4",
            size_bytes=2048,
            original_filename="video.mp4",
        ),
    }

    transcript = TranscriptFormatter.format_session(
        session=session,
        messages=messages,
        events=events,
        user_a_display="100234",
        user_b_display="100567",
        media_assets_by_id=media_map,
        timezone_str="UTC",
    )

    # 1. Header checks
    assert "LIKBY CHAT SESSION" in transcript
    assert "Session ID: cs_01K8XYZ" in transcript
    assert "User A (ID: 100234)" in transcript
    assert "User B (ID: 100567)" in transcript

    # 2. Chronological message lines
    assert "[2026-10-16 12:30:01] User A (100234): Hi!" in transcript
    assert "[2026-10-16 12:30:05] User B (100567): Hello 😊" in transcript
    assert "[2026-10-16 12:30:12] User A (100234): How was your day?" in transcript
    assert "[2026-10-16 12:30:20] User B (100567): It was great!" in transcript
    assert "[2026-10-16 12:30:25] User A (100234): [PHOTO: ast_01K8DEF_photo.jpg]" in transcript
    assert "[2026-10-16 12:30:30] User B (100567): [VIDEO: ast_01K8JKL_video.mp4]" in transcript

    # 3. System events
    assert "[2026-10-16 12:31:00] SYSTEM: Session reported." in transcript
    assert "[2026-10-16 12:31:05] SYSTEM: Report submitted for review." in transcript

    # 4. Footer & Counter checks
    assert "Session Status: REPORTED" in transcript
    assert "Total Messages: 6" in transcript
    assert "Media Attachments: 2" in transcript


def test_transcript_media_labels_and_unicode():
    """Verify document, audio, voice labels, captions, and emoji preservation."""
    session = ChatSession(
        id="cs_unicode_test",
        user_a_id="usr_01",
        user_b_id="usr_02",
        status=SessionStatus.ENDED,
        created_at=datetime(2026, 10, 16, 10, 0, 0, tzinfo=timezone.utc),
    )

    messages = [
        ChatMessage(
            id="msg_doc",
            session_id=session.id,
            sender_id="usr_01",
            sender_display_id="LK-01",
            sequence=1,
            message_type=MessageType.DOCUMENT,
            media_asset_id="ast_doc1",
            text="Resume doc",
            created_at=datetime(2026, 10, 16, 10, 1, 0, tzinfo=timezone.utc),
        ),
        ChatMessage(
            id="msg_voice",
            session_id=session.id,
            sender_id="usr_02",
            sender_display_id="LK-02",
            sequence=2,
            message_type=MessageType.VOICE,
            media_asset_id="ast_voice1",
            text=None,
            created_at=datetime(2026, 10, 16, 10, 2, 0, tzinfo=timezone.utc),
        ),
        ChatMessage(
            id="msg_emoji",
            session_id=session.id,
            sender_id="usr_01",
            sender_display_id="LK-01",
            sequence=3,
            message_type=MessageType.TEXT,
            text="🎉 Special unicode: नमस्ते, 🚀, ❤️, 한국어",
            created_at=datetime(2026, 10, 16, 10, 3, 0, tzinfo=timezone.utc),
        ),
    ]

    media_map = {
        "ast_doc1": MediaAsset(
            id="ast_doc1",
            session_id=session.id,
            message_id="msg_doc",
            bucket="likby-media",
            original_filename="resume.pdf",
            mime_type="application/pdf",
            size_bytes=5000,
            object_key="key",
        ),
        "ast_voice1": MediaAsset(
            id="ast_voice1",
            session_id=session.id,
            message_id="msg_voice",
            bucket="likby-media",
            original_filename="voice.ogg",
            mime_type="audio/ogg",
            size_bytes=3000,
            object_key="key",
        ),
    }

    transcript = TranscriptFormatter.format_session(
        session=session,
        messages=messages,
        user_a_display="LK-01",
        user_b_display="LK-02",
        media_assets_by_id=media_map,
        timezone_str="UTC",
    )

    assert "[DOCUMENT: ast_doc1_resume.pdf] - Resume doc" in transcript
    assert "[VOICE: ast_voice1_voice.ogg]" in transcript
    assert "🎉 Special unicode: नमस्ते, 🚀, ❤️, 한국어" in transcript
    assert "Total Messages: 3" in transcript
    assert "Media Attachments: 2" in transcript
    assert "Session Status: ENDED" in transcript
