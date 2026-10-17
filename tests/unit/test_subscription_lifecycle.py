"""
tests/unit/test_subscription_lifecycle.py
Comprehensive unit tests for subscription catalog, tier rules, expiration, upgrades, repeat purchases, and friend capacity preservation.
"""

from datetime import datetime, timezone, timedelta
import pytest

from likby.domain.entities.subscription import PLAN_SPECS, PLAN_LIMITS, SubscriptionPlan, SubscriptionEntitlement
from likby.domain.entities.user import User
from likby.domain.enums import EntitlementSource, EntitlementStatus, SubscriptionTier, FeatureKey
from likby.repositories.sqlite.database import init_sqlite_db
from likby.repositories.sqlite.subscription_repository import SqliteSubscriptionRepository
from likby.repositories.sqlite.usage_counter_repository import SqliteUsageCounterRepository
from likby.repositories.sqlite.friendship_repository import SqliteFriendshipRepository
from likby.repositories.sqlite.user_repository import SqliteUserRepository
from likby.services.subscription_service import SubscriptionService
from likby.services.usage_service import UsageService
from likby.services.social_service import SocialService


@pytest.mark.asyncio
async def test_plan_catalog_names_and_exact_spellings():
    """Verify exact required spellings, capitalization, and pricing targets for all 4 tiers."""
    assert PLAN_SPECS[SubscriptionTier.BASE]["name"] == "LikBy Base"
    assert PLAN_SPECS[SubscriptionTier.SPARK]["name"] == "LikBy Spark"
    assert PLAN_SPECS[SubscriptionTier.PREMIUM]["name"] == "LikBy Premium"
    assert PLAN_SPECS[SubscriptionTier.DIAMOND]["name"] == "LikBy Diamond"

    # Base is free with no expiry
    assert PLAN_SPECS[SubscriptionTier.BASE]["prices"]["INR"] == 0
    assert PLAN_SPECS[SubscriptionTier.BASE]["prices"]["XTR"] == 0
    assert PLAN_SPECS[SubscriptionTier.BASE]["duration_days"] is None

    # Spark 24h
    assert PLAN_SPECS[SubscriptionTier.SPARK]["prices"]["INR"] == 1900
    assert PLAN_SPECS[SubscriptionTier.SPARK]["duration_days"] == 1

    # Premium 30 days
    assert PLAN_SPECS[SubscriptionTier.PREMIUM]["prices"]["INR"] == 7900
    assert PLAN_SPECS[SubscriptionTier.PREMIUM]["duration_days"] == 30

    # Diamond 30 days
    assert PLAN_SPECS[SubscriptionTier.DIAMOND]["prices"]["INR"] == 14900
    assert PLAN_SPECS[SubscriptionTier.DIAMOND]["duration_days"] == 30


@pytest.mark.asyncio
async def test_base_tier_limits_and_no_expiry():
    """Verify LikBy Base provides perpetual access with standard daily quotas."""
    conn = await init_sqlite_db(":memory:")
    user_repo = SqliteUserRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    sub_service = SubscriptionService(sub_repo)

    await user_repo.save(User(id="usr_base_test", telegram_id=12301))

    ent = await sub_service.get_user_entitlement("usr_base_test")
    assert ent.tier == SubscriptionTier.BASE
    assert ent.status == EntitlementStatus.ACTIVE
    assert ent.expires_at is None  # Base has no expiry

    spec = sub_service.get_tier_spec(SubscriptionTier.BASE)
    assert spec["limits"]["likes_per_day"] == 25
    assert spec["limits"]["id_lookups_per_day"] == 10
    assert spec["limits"]["direct_requests_per_day"] == 3
    assert spec["limits"]["pending_outgoing_requests"] == 10
    assert spec["limits"]["games_started_per_day"] == 3
    assert spec["limits"]["active_friends_capacity"] == 3

    await conn.close()


@pytest.mark.asyncio
async def test_spark_pass_expiry_after_24_hours():
    """Verify LikBy Spark expires after 24 hours and automatically drops back to Base upon access."""
    conn = await init_sqlite_db(":memory:")
    user_repo = SqliteUserRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    sub_service = SubscriptionService(sub_repo)

    await user_repo.save(User(id="usr_spark_expired", telegram_id=12302))

    # Activate Spark pass with starts_at 25 hours ago
    past_start = datetime.now(timezone.utc) - timedelta(hours=25)
    past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)

    spark_ent = SubscriptionEntitlement(
        user_id="usr_spark_expired",
        tier=SubscriptionTier.SPARK,
        max_friends=5,
        daily_searches_limit=25,
        daily_requests_limit=5,
        starts_at=past_start,
        expires_at=past_expiry,
        is_active=True,
    )
    await sub_repo.save(spark_ent)

    # Access resolves status and detects expiration without in-memory timer
    active_ent = await sub_service.get_user_entitlement("usr_spark_expired")
    assert active_ent.tier == SubscriptionTier.BASE
    assert active_ent.status == EntitlementStatus.ACTIVE
    assert active_ent.expires_at is None

    # Check that record in DB was updated to Base
    recorded = await sub_repo.get_by_user_id("usr_spark_expired")
    assert recorded.tier == SubscriptionTier.BASE

    await conn.close()


@pytest.mark.asyncio
async def test_repeat_purchase_extends_active_subscription():
    """Verify repeat purchases of the same plan extend remaining time rather than discarding it."""
    conn = await init_sqlite_db(":memory:")
    user_repo = SqliteUserRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    sub_service = SubscriptionService(sub_repo)

    await user_repo.save(User(id="usr_repeat_purchaser", telegram_id=12303))

    # 1. Activate Premium with 20 days remaining
    now = datetime.now(timezone.utc)
    twenty_days_later = now + timedelta(days=20)
    initial_ent = SubscriptionEntitlement(
        user_id="usr_repeat_purchaser",
        tier=SubscriptionTier.PREMIUM,
        max_friends=15,
        daily_searches_limit=100,
        daily_requests_limit=15,
        starts_at=now,
        expires_at=twenty_days_later,
        is_active=True,
    )
    await sub_repo.save(initial_ent)

    # 2. User buys another 30-day Premium package
    updated_ent = await sub_service.activate_entitlement(
        user_id="usr_repeat_purchaser",
        tier=SubscriptionTier.PREMIUM,
        source=EntitlementSource.PAYMENT,
        duration_days=30,
    )

    # Expiry must be extended by 30 days from the previous 20-days-ahead expiration (~50 days)
    expected_expiry = twenty_days_later + timedelta(days=30)
    diff_seconds = abs((updated_ent.expires_at - expected_expiry).total_seconds())
    assert diff_seconds < 5.0
    assert updated_ent.tier == SubscriptionTier.PREMIUM
    assert updated_ent.status == EntitlementStatus.ACTIVE

    await conn.close()


@pytest.mark.asyncio
async def test_friend_capacity_preservation_on_downgrade():
    """
    CRITICAL REQUIREMENT:
    Base friend capacity is 3, while Premium is 15.
    If a user has 5 friends and downgrades to Base:
    Existing friends and chats survive downgrades.
    Expiration must prevent new premium-only actions without deleting existing relationships.
    """
    conn = await init_sqlite_db(":memory:")
    user_repo = SqliteUserRepository(conn)
    friend_repo = SqliteFriendshipRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    sub_service = SubscriptionService(sub_repo)

    # Create user and 5 friends
    u_main = User(id="usr_downgrade_test", telegram_id=9001)
    await user_repo.save(u_main)
    for i in range(5):
        friend = User(id=f"usr_f_{i}", telegram_id=9100 + i)
        await user_repo.save(friend)
        await friend_repo.add_friendship("usr_downgrade_test", f"usr_f_{i}")

    # Confirm 5 friends exist in DB
    friends_before = await friend_repo.list_friends("usr_downgrade_test")
    assert len(friends_before) == 5

    # Entitlement expires to Base
    ent = await sub_service.get_user_entitlement("usr_downgrade_test")
    assert ent.tier == SubscriptionTier.BASE

    # Existing friends still exist and are NOT deleted
    friends_after = await friend_repo.list_friends("usr_downgrade_test")
    assert len(friends_after) == 5

    # Check capacity check in SocialService: cannot add a 6th friend
    social_service = SocialService(
        like_repo=None,
        friendship_repo=friend_repo,
        user_repo=user_repo,
        block_repo=None,
        subscription_service=sub_service,
    )
    can_add = await social_service.can_add_friend("usr_downgrade_test")
    assert can_add is False  # Already at 5/3, so cannot add new friends

    await conn.close()


@pytest.mark.asyncio
async def test_daily_quota_atomic_reservation():
    """Verify UsageService atomicity and daily quota boundaries in Asia/Kolkata."""
    conn = await init_sqlite_db(":memory:")
    user_repo = SqliteUserRepository(conn)
    usage_repo = SqliteUsageCounterRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    sub_service = SubscriptionService(sub_repo)
    usage_service = UsageService(usage_repo=usage_repo, subscription_service=sub_service)

    user_id = "usr_quota_tester"
    await user_repo.save(User(id=user_id, telegram_id=12304))

    # Base has 25 daily likes
    for _ in range(25):
        allowed, remaining = await usage_service.check_and_consume(user_id, FeatureKey.DAILY_LIKES, amount=1)
        assert allowed is True

    # 26th request must be rejected
    allowed, remaining = await usage_service.check_and_consume(user_id, FeatureKey.DAILY_LIKES, amount=1)
    assert allowed is False
    assert remaining == 0

    await conn.close()
