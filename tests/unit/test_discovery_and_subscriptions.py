"""
tests.unit.test_discovery_and_subscriptions
Unit tests for ID search quotas, connection requests, and centralized subscription tiers.
"""

from datetime import datetime, timezone, timedelta
import pytest

from likby.domain.entities.user import User
from likby.domain.enums import ConnectionRequestStatus, PresenceStatus, SubscriptionTier
from likby.repositories.sqlite.block_repository import SqliteBlockRepository
from likby.repositories.sqlite.connection_request_repository import SqliteConnectionRequestRepository
from likby.repositories.sqlite.daily_usage_repository import SqliteDailyUsageRepository
from likby.repositories.sqlite.database import init_sqlite_db
from likby.repositories.sqlite.friendship_repository import SqliteFriendshipRepository
from likby.repositories.sqlite.subscription_repository import SqliteSubscriptionRepository
from likby.repositories.sqlite.user_repository import SqliteUserRepository
from likby.services.discovery_service import DiscoveryService
from likby.services.subscription_service import SubscriptionService


@pytest.mark.asyncio
async def test_id_search_daily_quota_and_upgrade(tmp_path):
    """Test daily search quotas on Free tier and capacity expansion on upgrade."""
    db_file = tmp_path / "test_discovery.db"
    conn = await init_sqlite_db(str(db_file))

    user_repo = SqliteUserRepository(conn)
    usage_repo = SqliteDailyUsageRepository(conn)
    req_repo = SqliteConnectionRequestRepository(conn)
    friendship_repo = SqliteFriendshipRepository(conn)
    block_repo = SqliteBlockRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)

    sub_service = SubscriptionService(sub_repo)
    discovery = DiscoveryService(
        user_repo=user_repo,
        daily_usage_repo=usage_repo,
        connection_request_repo=req_repo,
        friendship_repo=friendship_repo,
        block_repo=block_repo,
        subscription_service=sub_service,
    )

    u_searcher = User(id="usr_searcher", telegram_id=501)
    u_target = User(
        id="usr_target",
        telegram_id=502,
        unique_id="cryptowizard",
        presence=PresenceStatus.ACTIVE,
    )
    await user_repo.save(u_searcher)
    await user_repo.save(u_target)

    # 1. First 10 searches succeed (LikBy Base tier limit = 10)
    for i in range(10):
        ok, msg, preview = await discovery.search_user("usr_searcher", "cryptowizard")
        assert ok is True
        assert preview["display_id"] == "@cryptowizard"
        assert preview["presence"] == "Active recently"

    # 2. 11th search fails due to quota
    ok_11th, msg_11th, _ = await discovery.search_user("usr_searcher", "cryptowizard")
    assert ok_11th is False
    assert "quota reached" in msg_11th

    # 3. Upgrade to Premium expands limit to 100
    await sub_service.upgrade_tier("usr_searcher", SubscriptionTier.PREMIUM)
    limits = await sub_service.get_plan_limits("usr_searcher")
    assert limits["tier"] == "PREMIUM"
    assert limits["daily_searches_limit"] == 100

    # 4. Search now succeeds!
    ok_prem, msg_prem, _ = await discovery.search_user("usr_searcher", "cryptowizard")
    assert ok_prem is True

    await conn.close()


@pytest.mark.asyncio
async def test_connection_request_lifecycle_and_acceptance(tmp_path):
    """Test connection request sending, limits, and acceptance into friendship."""
    db_file = tmp_path / "test_conn_req.db"
    conn = await init_sqlite_db(str(db_file))

    user_repo = SqliteUserRepository(conn)
    usage_repo = SqliteDailyUsageRepository(conn)
    req_repo = SqliteConnectionRequestRepository(conn)
    friendship_repo = SqliteFriendshipRepository(conn)
    block_repo = SqliteBlockRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)

    sub_service = SubscriptionService(sub_repo)
    discovery = DiscoveryService(
        user_repo=user_repo,
        daily_usage_repo=usage_repo,
        connection_request_repo=req_repo,
        friendship_repo=friendship_repo,
        block_repo=block_repo,
        subscription_service=sub_service,
    )

    u1 = User(id="usr_alice", telegram_id=601, unique_id="alice")
    u2 = User(id="usr_bob", telegram_id=602, unique_id="bob")
    await user_repo.save(u1)
    await user_repo.save(u2)

    # 1. Send request
    ok, msg, req = await discovery.send_connection_request(u1.id, u2.id)
    assert ok is True
    assert req.status == ConnectionRequestStatus.PENDING

    # 2. Incoming requests for Bob
    incoming = await discovery.get_incoming_requests(u2.id)
    assert len(incoming) == 1
    assert incoming[0]["sender_id"] == u1.id

    # 3. Accept request -> Forms canonical friendship
    acc_ok, acc_msg, friendship = await discovery.accept_connection_request(req.id, u2.id)
    assert acc_ok is True
    assert friendship is not None
    assert friendship.id == "frd_usr_alice_usr_bob"
    assert friendship.source == "CONNECTION_REQUEST"

    # Verify friend count is now 1 for both
    assert await friendship_repo.count_user_friends(u1.id) == 1
    assert await friendship_repo.count_user_friends(u2.id) == 1

    await conn.close()
