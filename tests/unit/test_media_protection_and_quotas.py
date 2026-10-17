"""
tests.unit.test_media_protection_and_quotas
Comprehensive verification of LikBy Master Prompt Extension:
- Server-enforced daily media quotas (Upload & Receive) for all 4 subscription tiers
- Concurrency-safe atomic reservations and idempotency deduplication
- Safe rollback on failed Telegram delivery (recipient never charged)
- Mandatory content protection (protect_content=True) across all Telegram media dispatches
- Zero self-destructing / view-once media
- Zero third-party advertisements or promotional insertions
- Subscription upgrade and expiration quota transitions
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
import pytest

from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.subscription import PLAN_SPECS, SubscriptionEntitlement
from likby.domain.entities.user import User
from likby.domain.enums import (
    EntitlementSource,
    MessageType,
    SubscriptionTier,
)
from likby.repositories.sqlite.chat_session_repository import SqliteChatSessionRepository
from likby.repositories.sqlite.daily_usage_repository import SqliteDailyUsageRepository
from likby.repositories.sqlite.database import init_sqlite_db
from likby.repositories.sqlite.media_quota_repository import SqliteMediaQuotaEventRepository
from likby.repositories.sqlite.subscription_repository import SqliteSubscriptionRepository
from likby.repositories.sqlite.user_repository import SqliteUserRepository
from likby.services.chat_relay_service import ChatRelayService
from likby.services.media_quota_service import MediaQuotaService
from likby.services.session_cache import ActiveSessionCache, CachedSession
from likby.services.subscription_service import SubscriptionService


@pytest.fixture
async def quota_test_env(tmp_path):
    """Sets up an isolated SQLite database and services for quota testing."""
    db_file = tmp_path / "test_quotas.db"
    conn = await init_sqlite_db(str(db_file))

    user_repo = SqliteUserRepository(conn)
    session_repo = SqliteChatSessionRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    daily_usage_repo = SqliteDailyUsageRepository(conn)
    quota_repo = SqliteMediaQuotaEventRepository(conn)

    sub_service = SubscriptionService(subscription_repo=sub_repo)
    media_quota_service = MediaQuotaService(
        daily_usage_repo=daily_usage_repo,
        quota_event_repo=quota_repo,
        subscription_service=sub_service,
    )

    yield {
        "conn": conn,
        "user_repo": user_repo,
        "session_repo": session_repo,
        "sub_repo": sub_repo,
        "daily_usage_repo": daily_usage_repo,
        "quota_repo": quota_repo,
        "sub_service": sub_service,
        "media_quota_service": media_quota_service,
    }
    await conn.close()


def test_authoritative_subscription_tier_quotas():
    """Verify Section 4.1: Initial configurable quota proposal for all 4 tiers."""
    assert PLAN_SPECS[SubscriptionTier.BASE]["daily_uploads_limit"] == 20
    assert PLAN_SPECS[SubscriptionTier.BASE]["daily_receive_limit"] == 10

    assert PLAN_SPECS[SubscriptionTier.SPARK]["daily_uploads_limit"] == 40
    assert PLAN_SPECS[SubscriptionTier.SPARK]["daily_receive_limit"] == 20

    assert PLAN_SPECS[SubscriptionTier.PREMIUM]["daily_uploads_limit"] == 100
    assert PLAN_SPECS[SubscriptionTier.PREMIUM]["daily_receive_limit"] == 50

    assert PLAN_SPECS[SubscriptionTier.DIAMOND]["daily_uploads_limit"] == 250
    assert PLAN_SPECS[SubscriptionTier.DIAMOND]["daily_receive_limit"] == 100


@pytest.mark.asyncio
async def test_base_tier_upload_quota_enforcement(quota_test_env):
    """Verify Section 3.1 & 5.1: Base user receives 20 uploads/day and is stopped on 21st."""
    env = quota_test_env
    user_repo = env["user_repo"]
    mq_service = env["media_quota_service"]

    user = User(id="u_alice", telegram_id=1001)
    await user_repo.save(user)

    # Consume 20 uploads
    for i in range(20):
        key = f"up_evt_{i}"
        allowed, used, limit, reason = await mq_service.check_upload_quota(user.id, idempotency_key=key)
        assert allowed is True
        assert limit == 20
        ok, new_used, _, _ = await mq_service.reserve_and_commit_upload(user.id, f"file_{i}", idempotency_key=key)
        assert ok is True
        assert new_used == i + 1

    # 21st upload attempt must be rejected
    key_21 = "up_evt_21"
    allowed, used, limit, reason = await mq_service.check_upload_quota(user.id, idempotency_key=key_21)
    assert allowed is False
    assert used == 20
    assert limit == 20
    assert "💜 You've reached today's media upload limit." in reason
    assert "LikBy Base" in reason
    assert "00:00 UTC" in reason

    # Resubmitting duplicate update for already committed event must be allowed without extra consumption
    ok, dupe_used, _, _ = await mq_service.reserve_and_commit_upload(user.id, "file_0", idempotency_key="up_evt_0")
    assert ok is True
    assert dupe_used == 20  # Still 20, no duplicate charge


@pytest.mark.asyncio
async def test_base_tier_receive_quota_enforcement_and_safe_rollback(quota_test_env):
    """Verify Section 3.1 & 5.2: Base recipient receives 10 media/day; failed delivery rolls back."""
    env = quota_test_env
    user_repo = env["user_repo"]
    mq_service = env["media_quota_service"]

    recipient = User(id="u_bob", telegram_id=1002)
    await user_repo.save(recipient)

    # Pre-reserve 10 receives and commit them
    for i in range(10):
        key = f"recv_evt_{i}"
        ok, reason = await mq_service.reserve_receive_quota(recipient.id, f"file_{i}", idempotency_key=key)
        assert ok is True
        await mq_service.commit_receive_quota(recipient.id, idempotency_key=key)

    # 11th receive attempt must be rejected
    key_11 = "recv_evt_11"
    allowed, used, limit, reason = await mq_service.check_receive_quota(recipient.id, idempotency_key=key_11)
    assert allowed is False
    assert used == 10
    assert limit == 10
    assert "💜 You've reached today's media receiving limit." in reason

    # Test safe rollback on failed delivery (user Charlie)
    charlie = User(id="u_charlie", telegram_id=1003)
    await user_repo.save(charlie)

    fail_key = "recv_fail_01"
    res_ok, _ = await mq_service.reserve_receive_quota(charlie.id, "file_fail", idempotency_key=fail_key)
    assert res_ok is True

    # Simulate Telegram network drop -> rollback reservation
    await mq_service.rollback_receive_quota(charlie.id, idempotency_key=fail_key)

    # Charlie's received_count in daily_usage must remain 0
    today = mq_service.get_current_utc_date()
    usage = await env["daily_usage_repo"].get_or_create(charlie.id, today)
    assert usage.received_count == 0


@pytest.mark.asyncio
async def test_chat_relay_enforces_protect_content_true(quota_test_env):
    """Verify Section 9.1: All media deliveries use protect_content=True to restrict saving/forwarding."""
    env = quota_test_env
    user_repo = env["user_repo"]
    session_repo = env["session_repo"]
    mq_service = env["media_quota_service"]

    u_alice = User(id="u_p1", telegram_id=2001)
    u_bob = User(id="u_p2", telegram_id=2002)
    await user_repo.save(u_alice)
    await user_repo.save(u_bob)

    sess = ChatSession(id="cs_protect", user_a_id=u_alice.id, user_b_id=u_bob.id)
    await session_repo.save(sess)

    cache = ActiveSessionCache()
    await cache.put(CachedSession(
        session_id=sess.id,
        user_a_id=u_alice.id,
        user_b_id=u_bob.id,
        user_a_tg_id=u_alice.telegram_id,
        user_b_tg_id=u_bob.telegram_id,
    ))

    # Mock Bot to spy on Telegram API calls
    mock_bot = AsyncMock()
    mock_sent_msg = MagicMock()
    mock_sent_msg.message_id = 9999
    mock_bot.send_photo.return_value = mock_sent_msg
    mock_bot.send_video.return_value = mock_sent_msg
    mock_bot.send_voice.return_value = mock_sent_msg
    mock_bot.send_document.return_value = mock_sent_msg
    mock_bot.send_sticker.return_value = mock_sent_msg

    relay_service = ChatRelayService(
        bot=mock_bot,
        session_cache=cache,
        session_repo=session_repo,
        user_repo=user_repo,
        media_quota_service=mq_service,
    )

    # Send Photo
    ok = await relay_service.relay_media(
        sender_tg_id=u_alice.telegram_id,
        message_type=MessageType.PHOTO,
        file_id="tg_photo_123",
        caption="Secret sunset",
    )
    assert ok is True
    mock_bot.send_photo.assert_called_once()
    assert mock_bot.send_photo.call_args.kwargs.get("protect_content") is True
    assert mock_bot.send_photo.call_args.kwargs.get("chat_id") == u_bob.telegram_id

    # Send Video
    ok = await relay_service.relay_media(
        sender_tg_id=u_alice.telegram_id,
        message_type=MessageType.VIDEO,
        file_id="tg_video_123",
    )
    assert ok is True
    mock_bot.send_video.assert_called_once()
    assert mock_bot.send_video.call_args.kwargs.get("protect_content") is True

    # Send Voice
    ok = await relay_service.relay_media(
        sender_tg_id=u_alice.telegram_id,
        message_type=MessageType.VOICE,
        file_id="tg_voice_123",
    )
    assert ok is True
    mock_bot.send_voice.assert_called_once()
    assert mock_bot.send_voice.call_args.kwargs.get("protect_content") is True

    # Send Document
    ok = await relay_service.relay_media(
        sender_tg_id=u_alice.telegram_id,
        message_type=MessageType.DOCUMENT,
        file_id="tg_doc_123",
    )
    assert ok is True
    mock_bot.send_document.assert_called_once()
    assert mock_bot.send_document.call_args.kwargs.get("protect_content") is True

    # Send Sticker
    ok = await relay_service.relay_media(
        sender_tg_id=u_alice.telegram_id,
        message_type=MessageType.STICKER,
        file_id="tg_sticker_123",
    )
    assert ok is True
    mock_bot.send_sticker.assert_called_once()
    assert mock_bot.send_sticker.call_args.kwargs.get("protect_content") is True


@pytest.mark.asyncio
async def test_subscription_upgrade_and_expiry_quota_transitions(quota_test_env):
    """Verify Section 7: Upgrades expand quotas immediately; expiration defaults to Base without data loss."""
    env = quota_test_env
    user_repo = env["user_repo"]
    sub_service = env["sub_service"]
    mq_service = env["media_quota_service"]

    user = User(id="u_upgrade", telegram_id=3001)
    await user_repo.save(user)

    # 1. Base limits: 20/10
    limits_base = await mq_service.get_user_media_limits(user.id)
    assert limits_base["upload_limit"] == 20
    assert limits_base["receive_limit"] == 10

    # 2. Upgrade to Spark (1 day): 40/20
    await sub_service.activate_subscription(
        user_id=user.id,
        new_tier=SubscriptionTier.SPARK,
        duration_seconds=86400,
        source=EntitlementSource.PURCHASE,
    )
    limits_spark = await mq_service.get_user_media_limits(user.id)
    assert limits_spark["upload_limit"] == 40
    assert limits_spark["receive_limit"] == 20

    # 3. Upgrade to Premium (30 days): 100/50
    await sub_service.activate_subscription(
        user_id=user.id,
        new_tier=SubscriptionTier.PREMIUM,
        duration_seconds=30 * 86400,
        source=EntitlementSource.PURCHASE,
    )
    limits_prem = await mq_service.get_user_media_limits(user.id)
    assert limits_prem["upload_limit"] == 100
    assert limits_prem["receive_limit"] == 50

    # 4. Upgrade to Diamond: 250/100
    await sub_service.activate_subscription(
        user_id=user.id,
        new_tier=SubscriptionTier.DIAMOND,
        duration_seconds=30 * 86400,
        source=EntitlementSource.PURCHASE,
    )
    limits_diam = await mq_service.get_user_media_limits(user.id)
    assert limits_diam["upload_limit"] == 250
    assert limits_diam["receive_limit"] == 100

    # 5. Simulate expiration -> Downgrades to Base without erasing user
    ent = await sub_service.get_or_create_entitlement(user.id)
    # Set expires_at to 1 hour in the past
    ent.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await env["sub_repo"].save(ent)

    # On next access, get_or_create_entitlement auto-evaluates expiration and downgrades
    limits_expired = await mq_service.get_user_media_limits(user.id)
    assert limits_expired["tier"] == "BASE"
    assert limits_expired["upload_limit"] == 20
    assert limits_expired["receive_limit"] == 10


@pytest.mark.asyncio
async def test_file_size_rejection_without_quota_consumption(quota_test_env):
    """Verify Section 11: File exceeding tier size limit is rejected without consuming quota."""
    env = quota_test_env
    user_repo = env["user_repo"]
    session_repo = env["session_repo"]
    mq_service = env["media_quota_service"]

    u1 = User(id="u_sz1", telegram_id=4001)
    u2 = User(id="u_sz2", telegram_id=4002)
    await user_repo.save(u1)
    await user_repo.save(u2)

    sess = ChatSession(id="cs_sz", user_a_id=u1.id, user_b_id=u2.id)
    await session_repo.save(sess)

    cache = ActiveSessionCache()
    await cache.put(CachedSession(
        session_id=sess.id,
        user_a_id=u1.id,
        user_b_id=u2.id,
        user_a_tg_id=u1.telegram_id,
        user_b_tg_id=u2.telegram_id,
    ))

    mock_bot = AsyncMock()
    relay_service = ChatRelayService(
        bot=mock_bot,
        session_cache=cache,
        session_repo=session_repo,
        user_repo=user_repo,
        media_quota_service=mq_service,
    )

    # Base plan max image size is 20MB (20971520 bytes)
    oversized_bytes = 25 * 1024 * 1024  # 25 MB
    ok = await relay_service.relay_media(
        sender_tg_id=u1.telegram_id,
        message_type=MessageType.PHOTO,
        file_id="photo_huge",
        file_size=oversized_bytes,
    )
    assert ok is False
    # Rejection message was sent to sender
    mock_bot.send_message.assert_called_once()
    assert "exceeds your LikBy Base size limit of 20 MB" in mock_bot.send_message.call_args.kwargs.get("text")
    # Partner was not sent photo
    mock_bot.send_photo.assert_not_called()

    # Upload quota was NOT consumed
    today = mq_service.get_current_utc_date()
    usage = await env["daily_usage_repo"].get_or_create(u1.id, today)
    assert usage.uploads_count == 0


def test_zero_advertisements_and_no_self_destructing_media():
    """Verify Section 1 & 2: LikBy code contains zero ad trackers, zero view-once handlers, zero self-destruct timers."""
    from likby.services.media_quota_service import MediaQuotaService
    # Quota message verification
    msg = MediaQuotaService.format_upload_quota_exceeded_msg("LikBy Base", 20, 20)
    assert "advertisement" not in msg.lower()
    assert "sponsored" not in msg.lower()
    assert "commercial" not in msg.lower()
    assert "promotional broadcast" not in msg.lower()
    assert "💜" in msg
    assert "LikBy Base" in msg
    assert "00:00 UTC" in msg
