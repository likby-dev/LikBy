"""
tests.integration.test_chat_sessions_api
Integration tests for Chat Sessions API endpoints:
- GET /api/v1/chat-sessions/{session_id}/transcript
- GET /api/v1/chat-sessions/{session_id}/messages
- GET /api/v1/chat-sessions/{session_id}/events
- GET /api/v1/chat-sessions/{session_id}/summary
- Security & IDOR authorization checks (participants vs unauthorized third-parties)
- Pagination and format query parameters
"""

import asyncio
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.media_asset import MediaAsset
from likby.domain.entities.message import ChatMessage
from likby.domain.entities.session_event import SessionEvent
from likby.domain.entities.user import User
from likby.domain.enums import MessageDeliveryStatus, MessageType, SessionStatus
from likby.main import app


@pytest.fixture
def test_setup():
    """Seed test users, session, messages, events, and media asset in app state."""
    user_a = User(id="usr_alice", telegram_id=900101, unique_id="LK-ALICE")
    user_b = User(id="usr_bob", telegram_id=900102, unique_id="LK-BOB")
    user_intruder = User(id="usr_intruder", telegram_id=900103, unique_id="LK-INTRUDER")

    session = ChatSession(
        id="cs_test_api_001",
        user_a_id=user_a.id,
        user_b_id=user_b.id,
        status=SessionStatus.REPORTED,
        created_at=datetime(2026, 10, 16, 12, 30, 0, tzinfo=timezone.utc),
    )

    messages = [
        ChatMessage(
            id="msg_api_01",
            session_id=session.id,
            sender_id=user_a.id,
            sender_display_id=user_a.unique_id,
            sequence=1,
            message_type=MessageType.TEXT,
            text="Hi Bob!",
            created_at=datetime(2026, 10, 16, 12, 30, 1, tzinfo=timezone.utc),
            delivery_status=MessageDeliveryStatus.DELIVERED,
        ),
        ChatMessage(
            id="msg_api_02",
            session_id=session.id,
            sender_id=user_b.id,
            sender_display_id=user_b.unique_id,
            sequence=2,
            message_type=MessageType.TEXT,
            text="Hey Alice! 😊",
            created_at=datetime(2026, 10, 16, 12, 30, 5, tzinfo=timezone.utc),
            delivery_status=MessageDeliveryStatus.DELIVERED,
        ),
        ChatMessage(
            id="msg_api_03",
            session_id=session.id,
            sender_id=user_a.id,
            sender_display_id=user_a.unique_id,
            sequence=3,
            message_type=MessageType.PHOTO,
            media_asset_id="ast_photo_01",
            text="Look at this sunset",
            created_at=datetime(2026, 10, 16, 12, 30, 25, tzinfo=timezone.utc),
            delivery_status=MessageDeliveryStatus.DELIVERED,
        ),
    ]

    events = [
        SessionEvent(
            id="evt_api_01",
            session_id=session.id,
            event_type="SESSION_REPORTED",
            display_text="Session reported.",
            sequence=4,
            created_at=datetime(2026, 10, 16, 12, 31, 0, tzinfo=timezone.utc),
        ),
        SessionEvent(
            id="evt_api_02",
            session_id=session.id,
            event_type="REPORT_SUBMITTED",
            display_text="Report submitted for review.",
            sequence=5,
            created_at=datetime(2026, 10, 16, 12, 31, 5, tzinfo=timezone.utc),
        ),
    ]

    media_asset = MediaAsset(
        id="ast_photo_01",
        session_id=session.id,
        message_id="msg_api_03",
        bucket="likby-media",
        original_filename="sunset.jpg",
        mime_type="image/jpeg",
        size_bytes=4096,
        object_key="likby/prod/ast_photo_01_sunset.jpg",
    )

    return {
        "user_a": user_a,
        "user_b": user_b,
        "user_intruder": user_intruder,
        "session": session,
        "messages": messages,
        "events": events,
        "media_asset": media_asset,
    }


def _seed_app_state(app_instance, data):
    """Helper to seed test data into app.state repositories."""
    asyncio.run(app_instance.state.user_repo.save(data["user_a"]))
    asyncio.run(app_instance.state.user_repo.save(data["user_b"]))
    asyncio.run(app_instance.state.session_repo.save(data["session"]))
    for m in data["messages"]:
        asyncio.run(app_instance.state.message_repo.save(m))
    for e in data["events"]:
        asyncio.run(app_instance.state.message_repo.save_event(
            session_id=e.session_id,
            event_id=e.id,
            event_type=e.event_type,
            display_text=e.display_text,
            sequence=e.sequence,
        ))
    if hasattr(app_instance.state, "media_repo") and app_instance.state.media_repo:
        asyncio.run(app_instance.state.media_repo.save(data["media_asset"]))


def test_transcript_endpoint_authorized_participant(test_setup):
    """Authorized participant can fetch the human-readable text transcript."""
    with TestClient(app) as client:
        _seed_app_state(app, test_setup)

        # 1. Plain text format (default)
        res = client.get(
            f"/api/v1/chat-sessions/{test_setup['session'].id}/transcript",
            headers={"X-User-Id": test_setup["user_a"].id},
        )
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/plain")
        body = res.text

        # Header
        assert "LIKBY CHAT SESSION" in body
        assert f"Session ID: {test_setup['session'].id}" in body
        assert f"User A (ID: {test_setup['user_a'].unique_id})" in body
        assert f"User B (ID: {test_setup['user_b'].unique_id})" in body

        # Content
        assert "User A (LK-ALICE): Hi Bob!" in body
        assert "User B (LK-BOB): Hey Alice! 😊" in body
        assert "[PHOTO: ast_photo_01_sunset.jpg] - Look at this sunset" in body
        assert "SYSTEM: Session reported." in body
        assert "SYSTEM: Report submitted for review." in body

        # Footer
        assert "Session Status: REPORTED" in body
        assert "Total Messages: 3" in body
        assert "Media Attachments: 1" in body

        # 2. JSON format
        res_json = client.get(
            f"/api/v1/chat-sessions/{test_setup['session'].id}/transcript?format=json",
            headers={"X-User-Id": test_setup["user_b"].id},
        )
        assert res_json.status_code == 200
        json_data = res_json.json()
        assert json_data["session_id"] == test_setup["session"].id
        assert json_data["status"] == "REPORTED"
        assert "LIKBY CHAT SESSION" in json_data["transcript"]


def test_transcript_endpoint_unauthorized_intruder_forbidden(test_setup):
    """A non-participant user cannot access or guess another session's transcript (IDOR prevention)."""
    with TestClient(app) as client:
        _seed_app_state(app, test_setup)
        asyncio.run(app.state.user_repo.save(test_setup["user_intruder"]))

        res = client.get(
            f"/api/v1/chat-sessions/{test_setup['session'].id}/transcript",
            headers={"X-User-Id": test_setup["user_intruder"].id},
        )
        assert res.status_code == 403
        assert "Access denied" in res.json()["detail"]


def test_transcript_endpoint_missing_auth_rejected():
    """Unauthenticated requests are rejected with 401 Unauthorized."""
    with TestClient(app) as client:
        res = client.get("/api/v1/chat-sessions/cs_random_id/transcript")
        assert res.status_code == 401


def test_chat_session_summary_and_pagination(test_setup):
    """Verify /summary, /messages, and /events paginated endpoints."""
    with TestClient(app) as client:
        _seed_app_state(app, test_setup)

        # Summary
        res_sum = client.get(
            f"/api/v1/chat-sessions/{test_setup['session'].id}/summary",
            headers={"X-User-Id": test_setup["user_a"].id},
        )
        assert res_sum.status_code == 200
        summary = res_sum.json()
        assert summary["session_id"] == test_setup["session"].id
        assert summary["status"] == "REPORTED"
        assert summary["message_count"] == 3
        assert summary["media_attachment_count"] == 1

        # Messages pagination
        res_msgs = client.get(
            f"/api/v1/chat-sessions/{test_setup['session'].id}/messages?limit=2&offset=0",
            headers={"X-User-Id": test_setup["user_a"].id},
        )
        assert res_msgs.status_code == 200
        msgs_data = res_msgs.json()
        assert msgs_data["limit"] == 2
        assert msgs_data["offset"] == 0
        assert len(msgs_data["messages"]) == 2
        assert msgs_data["messages"][0]["message_id"] == "msg_api_01"

        # Events pagination
        res_events = client.get(
            f"/api/v1/chat-sessions/{test_setup['session'].id}/events?limit=10&offset=0",
            headers={"X-User-Id": test_setup["user_b"].id},
        )
        assert res_events.status_code == 200
        events_data = res_events.json()
        assert len(events_data["events"]) == 2
        assert events_data["events"][0]["event_type"] == "SESSION_REPORTED"
        assert events_data["events"][0]["display_text"] == "Session reported."
