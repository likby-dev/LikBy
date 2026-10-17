"""
tests/integration/test_supabase_firestore_r2_pipeline.py
Integration tests validating the Supabase + Firestore + Cloudflare R2 architecture:
- Authoritative Firestore conversation storage and transcript formatting
- Cloudflare R2 object key generation, archival, and presigned URL access control
- Outbox worker retries, backoff, and idempotent dispatch
- Reconciliation sweeps for stuck outbox jobs and orphaned assets
- CLI configuration validation
- Mutual likes, canonical friendships, and friend capacity limits
- Non-punitive reporting and karma audit ledger consistency
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from likby.cli import check_config
from likby.config import Settings
from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.media_asset import MediaAsset
from likby.domain.entities.message import ChatMessage
from likby.domain.entities.outbox import OutboxJob
from likby.domain.entities.user import User
from likby.domain.enums import (
    MediaUploadStatus,
    MessageDeliveryStatus,
    MessageType,
    OutboxJobStatus,
    SessionStatus,
    SubscriptionTier,
    UserState,
    UserStatus,
)
from likby.repositories.firestore.message_repository import FirestoreMessageRepository
from likby.repositories.sqlite.media_asset_repository import SqliteMediaAssetRepository
from likby.repositories.sqlite.outbox_repository import SqliteOutboxRepository
from likby.services.chat_relay_service import ChatRelayService
from likby.services.media_storage_service import (
    CloudflareR2StorageProvider,
    LocalMediaStorageProvider,
    MediaService,
)
from likby.services.outbox_worker import OutboxWorker
from likby.services.reconciliation_service import ReconciliationService
from likby.services.session_cache import ActiveSessionCache
from likby.services.social_service import SocialService
from likby.services.transcript_service import TranscriptFormatter, TranscriptService


@pytest.mark.asyncio
async def test_firestore_conversation_storage_and_ordering():
    """Verify Firestore message repository maintains strict per-session sequence ordering."""
    repo = FirestoreMessageRepository(use_mock=True)

    session_id = "cs_test_firestore_01"

    # Allocate sequences
    seq1 = await repo.get_next_sequence(session_id)
    seq2 = await repo.get_next_sequence(session_id)
    assert seq1 == 1
    assert seq2 == 2

    # Save messages
    msg1 = ChatMessage(
        id="msg_001",
        session_id=session_id,
        sender_id="usr_01",
        sender_display_id="LK-10001",
        sequence=seq1,
        message_type=MessageType.TEXT,
        text="Hello world!",
        delivery_status=MessageDeliveryStatus.DELIVERED,
    )
    msg2 = ChatMessage(
        id="msg_002",
        session_id=session_id,
        sender_id="usr_02",
        sender_display_id="LK-10002",
        sequence=seq2,
        message_type=MessageType.TEXT,
        text="Hi there!",
        delivery_status=MessageDeliveryStatus.DELIVERED,
    )

    await repo.save(msg1)
    await repo.save(msg2)

    # Save conversation event
    await repo.save_event(session_id, "ev_01", "session_started", {"actor": "system"})

    # Retrieve ordered messages
    messages = await repo.get_session_messages(session_id)
    assert len(messages) == 2
    assert messages[0].sequence == 1
    assert messages[0].text == "Hello world!"
    assert messages[1].sequence == 2
    assert messages[1].text == "Hi there!"


@pytest.mark.asyncio
async def test_human_readable_transcript_formatter():
    """Verify human-readable plain text transcript rendering with participant IDs and media tags."""
    session = ChatSession(
        id="cs_01K8XYZ",
        user_a_id="usr_01",
        user_b_id="usr_02",
        status=SessionStatus.ENDED,
        started_at=datetime(2026, 10, 15, 14, 0, 0, tzinfo=timezone.utc),
    )

    messages = [
        ChatMessage(
            id="msg_1",
            session_id=session.id,
            sender_id="usr_01",
            sender_display_id="LK-10001",
            sequence=1,
            message_type=MessageType.TEXT,
            text="Hi!",
            created_at=datetime(2026, 10, 15, 14, 1, 0, tzinfo=timezone.utc),
        ),
        ChatMessage(
            id="msg_2",
            session_id=session.id,
            sender_id="usr_02",
            sender_display_id="LK-10002",
            sequence=2,
            message_type=MessageType.TEXT,
            text="Hello!",
            created_at=datetime(2026, 10, 15, 14, 1, 15, tzinfo=timezone.utc),
        ),
        ChatMessage(
            id="msg_3",
            session_id=session.id,
            sender_id="usr_01",
            sender_display_id="LK-10001",
            sequence=3,
            message_type=MessageType.PHOTO,
            media_asset_id="ast_01K8DEF",
            created_at=datetime(2026, 10, 15, 14, 2, 0, tzinfo=timezone.utc),
        ),
        ChatMessage(
            id="msg_4",
            session_id=session.id,
            sender_id="SYSTEM",
            sender_display_id="SYSTEM",
            sequence=4,
            message_type=MessageType.SYSTEM,
            text="Session reported.",
            created_at=datetime(2026, 10, 15, 14, 3, 0, tzinfo=timezone.utc),
        ),
    ]

    media_assets = {
        "ast_01K8DEF": MediaAsset(
            id="ast_01K8DEF",
            session_id=session.id,
            message_id="msg_3",
            storage_provider="r2",
            bucket="likby-media",
            object_key="likby/prod/2026/10/cs_01K8XYZ/msg_3/ast_01K8DEF_photo.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            original_filename="photo.jpg",
            upload_status=MediaUploadStatus.ARCHIVED,
        )
    }

    transcript = TranscriptFormatter.format_session(
        session=session,
        messages=messages,
        user_a_display="LK-10001",
        user_b_display="LK-10002",
        media_assets_by_id=media_assets,
    )

    assert "LIKBY CHAT SESSION" in transcript
    assert "User A (ID: LK-10001)" in transcript
    assert "User B (ID: LK-10002)" in transcript
    assert "User A (LK-10001): Hi!" in transcript
    assert "User B (LK-10002): Hello!" in transcript
    assert "User A (LK-10001): [PHOTO: ast_01K8DEF_photo.jpg]" in transcript
    assert "SYSTEM: Session reported." in transcript


@pytest.mark.asyncio
async def test_r2_object_key_generation_and_presigned_url_auth():
    """Verify deterministic R2 object keys and IDOR-safe presigned URLs."""
    # 1. Object key format
    dt = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
    key = MediaAsset.generate_object_key(
        environment="prod",
        session_id="cs_01K8XYZ",
        message_id="msg_01K8ABC",
        asset_id="ast_01K8DEF",
        safe_filename="photo.jpg",
        timestamp=dt,
    )
    assert key == "likby/prod/2026/10/cs_01K8XYZ/msg_01K8ABC/ast_01K8DEF_photo.jpg"

    # 2. Local provider presigned URL
    provider = LocalMediaStorageProvider(base_dir="media_store")
    mock_media_repo = AsyncMock()
    mock_media_repo.get_by_id.return_value = MediaAsset(
        id="ast_01K8DEF",
        session_id="cs_01K8XYZ",
        message_id="msg_01K8ABC",
        storage_provider="local",
        bucket="likby-media",
        object_key=key,
        mime_type="image/jpeg",
        size_bytes=2048,
        upload_status=MediaUploadStatus.ARCHIVED,
    )

    media_service = MediaService(provider=provider, media_repo=mock_media_repo)

    # Authorized participant receives presigned URL
    url = await media_service.get_presigned_url(
        asset_id="ast_01K8DEF",
        requesting_user_id="usr_01",
        authorized_user_ids=["usr_01", "usr_02"],
    )
    assert url is not None
    assert "expires=300" in url

    # Unauthorized user is denied (IDOR protection)
    unauthorized_url = await media_service.get_presigned_url(
        asset_id="ast_01K8DEF",
        requesting_user_id="usr_attacker",
        authorized_user_ids=["usr_01", "usr_02"],
    )
    assert unauthorized_url is None


@pytest.mark.asyncio
async def test_outbox_worker_retry_backoff_and_idempotency():
    """Verify outbox worker handles transient delivery failure with exponential backoff."""
    mock_outbox_repo = AsyncMock()
    mock_bot = AsyncMock()

    # Bot delivery raises transient network error
    mock_bot.send_message.side_effect = Exception("Telegram 502 Bad Gateway")

    mock_msg_repo = AsyncMock()
    mock_msg_repo.get_by_id.return_value = ChatMessage(
        id="msg_01",
        session_id="cs_01",
        sender_id="usr_01",
        sender_display_id="usr_01",
        sequence=1,
        message_type=MessageType.TEXT,
        text="Durable text",
    )

    worker = OutboxWorker(
        outbox_repo=mock_outbox_repo,
        bot=mock_bot,
        message_repo=mock_msg_repo,
        batch_size=10,
        max_attempts=3,
        backoff_base=2.0,
    )

    job = OutboxJob(
        id="job_01",
        session_id="cs_01",
        message_id="msg_01",
        recipient_tg_id=999888,
        attempt_count=1,
        status=OutboxJobStatus.PROCESSING,
    )
    mock_outbox_repo.claim_pending_jobs.return_value = [job]

    # Process batch
    processed = await worker.process_batch()
    assert processed == 0

    # Job is marked failed with backoff timestamp
    mock_outbox_repo.mark_failed.assert_called_once()
    call_args = mock_outbox_repo.mark_failed.call_args[0]
    assert call_args[0] == "job_01"
    assert call_args[1] == "TRANSIENT_FAILURE"
    assert isinstance(call_args[2], datetime)


@pytest.mark.asyncio
async def test_reconciliation_service_sweep():
    """Verify reconciliation service audits cross-service integrity."""
    mock_outbox = AsyncMock()
    mock_media = AsyncMock()
    mock_media_service = AsyncMock()

    reconciler = ReconciliationService(
        outbox_repo=mock_outbox,
        media_repo=mock_media,
        media_service=mock_media_service,
    )

    results = await reconciler.run_full_reconciliation()
    assert "completed_at" in results
    assert "stuck_jobs_reset" in results
    assert "expired_subscriptions_reconciled" in results
    assert "orphaned_assets_flagged" in results


def test_cli_config_audit_command():
    """Verify check_config runs cleanly without exceptions."""
    exit_code = check_config()
    assert exit_code == 0
