"""
tests.integration.test_new_repositories
Integration tests for new SQLite repositories (messages, media, social, karma, subscriptions).
"""

from datetime import datetime, timezone
import pytest

from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.connection_request import ConnectionRequest
from likby.domain.entities.daily_usage import DailyUsage
from likby.domain.entities.friendship import Friendship
from likby.domain.entities.karma import KarmaLedgerEntry
from likby.domain.entities.like import Like
from likby.domain.entities.media_asset import MediaAsset
from likby.domain.entities.message import ChatMessage
from likby.domain.entities.outbox import OutboxJob
from likby.domain.entities.rating import SessionRating
from likby.domain.entities.subscription import SubscriptionEntitlement
from likby.domain.entities.user import User
from likby.domain.enums import (
    ConnectionRequestStatus,
    FriendshipStatus,
    KarmaSourceType,
    MediaUploadStatus,
    MessageDeliveryStatus,
    MessageType,
    OutboxJobStatus,
    RatingType,
    SubscriptionTier,
)
from likby.repositories.sqlite.connection_request_repository import SqliteConnectionRequestRepository
from likby.repositories.sqlite.daily_usage_repository import SqliteDailyUsageRepository
from likby.repositories.sqlite.database import init_sqlite_db
from likby.repositories.sqlite.friendship_repository import SqliteFriendshipRepository
from likby.repositories.sqlite.karma_repository import SqliteKarmaRepository
from likby.repositories.sqlite.like_repository import SqliteLikeRepository
from likby.repositories.sqlite.media_asset_repository import SqliteMediaAssetRepository
from likby.repositories.sqlite.message_repository import SqliteMessageRepository
from likby.repositories.sqlite.outbox_repository import SqliteOutboxRepository
from likby.repositories.sqlite.rating_repository import SqliteRatingRepository
from likby.repositories.sqlite.subscription_repository import SqliteSubscriptionRepository
from likby.repositories.sqlite.user_repository import SqliteUserRepository
from likby.repositories.sqlite.chat_session_repository import SqliteChatSessionRepository


@pytest.mark.asyncio
async def test_message_and_outbox_repositories(tmp_path):
    """Test ChatMessage persistence, deterministic sequencing, and transactional outbox jobs."""
    db_file = tmp_path / "test_msg_repo.db"
    conn = await init_sqlite_db(str(db_file))

    msg_repo = SqliteMessageRepository(conn)
    outbox_repo = SqliteOutboxRepository(conn)
    user_repo = SqliteUserRepository(conn)
    session_repo = SqliteChatSessionRepository(conn)

    # Insert prerequisite users and session
    await user_repo.save(User(id="usr_01", telegram_id=10001))
    await user_repo.save(User(id="usr_02", telegram_id=10002))
    await session_repo.save(ChatSession(id="cs_01", user_a_id="usr_01", user_b_id="usr_02"))

    # 1. Message sequencing
    seq1 = await msg_repo.get_next_sequence("cs_01")
    assert seq1 == 1

    msg = ChatMessage(
        id="msg_01",
        session_id="cs_01",
        sender_id="usr_01",
        sender_display_id="LK-10001",
        sequence=seq1,
        message_type=MessageType.TEXT,
        text="Hello world!",
        delivery_status=MessageDeliveryStatus.PENDING,
    )
    await msg_repo.save(msg)

    seq2 = await msg_repo.get_next_sequence("cs_01")
    assert seq2 == 2

    # 2. Retrieval and status update
    retrieved = await msg_repo.get_by_id("msg_01")
    assert retrieved is not None
    assert retrieved.text == "Hello world!"

    await msg_repo.update_delivery_status("msg_01", MessageDeliveryStatus.DELIVERED, telegram_msg_id=999)
    updated = await msg_repo.get_by_id("msg_01")
    assert updated.delivery_status == MessageDeliveryStatus.DELIVERED
    assert updated.telegram_message_id == 999

    # 3. Outbox job persistence
    job = OutboxJob(
        id="job_01",
        session_id="cs_01",
        message_id="msg_01",
        recipient_tg_id=123456,
        status=OutboxJobStatus.PENDING,
    )
    await outbox_repo.save(job)

    pending_jobs = await outbox_repo.get_pending_jobs()
    assert len(pending_jobs) == 1
    assert pending_jobs[0].recipient_tg_id == 123456

    job.mark_completed()
    await outbox_repo.update_job(job)
    pending_after = await outbox_repo.get_pending_jobs()
    assert len(pending_after) == 0

    await conn.close()


@pytest.mark.asyncio
async def test_social_and_subscription_repositories(tmp_path):
    """Test Likes, Friendships, Connection Requests, and Subscriptions CRUD."""
    db_file = tmp_path / "test_social_repo.db"
    conn = await init_sqlite_db(str(db_file))

    like_repo = SqliteLikeRepository(conn)
    friend_repo = SqliteFriendshipRepository(conn)
    req_repo = SqliteConnectionRequestRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    usage_repo = SqliteDailyUsageRepository(conn)
    user_repo = SqliteUserRepository(conn)

    # Insert prerequisite users for foreign keys
    await user_repo.save(User(id="u1", telegram_id=101))
    await user_repo.save(User(id="u2", telegram_id=102))
    await user_repo.save(User(id="u3", telegram_id=103))

    # 1. Like
    like = Like(id="lik_01", sender_id="u1", target_id="u2")
    await like_repo.save(like)
    fetched_like = await like_repo.get_like("u1", "u2")
    assert fetched_like is not None
    assert fetched_like.is_active is True

    # 2. Canonical Friendship
    f = Friendship.create("u1", "u2")
    await friend_repo.save(f)
    assert await friend_repo.count_user_friends("u1") == 1
    assert await friend_repo.count_user_friends("u2") == 1

    # 3. Connection Request
    req = ConnectionRequest(id="req_01", sender_id="u3", target_id="u1")
    await req_repo.save(req)
    pending_between = await req_repo.get_pending_between("u3", "u1")
    assert pending_between is not None

    # 4. Subscription Entitlement
    ent = SubscriptionEntitlement.create_default_free("u1")
    await sub_repo.save(ent)
    fetched_ent = await sub_repo.get_by_user_id("u1")
    assert fetched_ent is not None
    assert fetched_ent.tier == SubscriptionTier.FREE
    assert fetched_ent.max_friends == 3

    # 5. Daily Usage
    today = "2026-10-16"
    usage = await usage_repo.get_or_create("u1", today)
    assert usage.searches_count == 0

    new_count = await usage_repo.increment_search("u1", today)
    assert new_count == 1

    await conn.close()
