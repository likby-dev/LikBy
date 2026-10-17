"""
tests/unit/test_gaming_entitlements.py
Unit tests for GamingEntitlementService, subscription-based daily duel limits,
unlimited solo game access, and atomic two-player quota consumption.
"""

from datetime import datetime, timezone
import pytest

from likby.domain.entities.user import User
from likby.domain.enums import GameType, SubscriptionTier
from likby.repositories.sqlite.database import init_sqlite_db
from likby.repositories.sqlite.play_game_repository import SqliteDuelQuotaRepository
from likby.repositories.sqlite.subscription_repository import SqliteSubscriptionRepository
from likby.repositories.sqlite.user_repository import SqliteUserRepository
from likby.services.gaming_entitlement_service import GamingEntitlementService
from likby.services.subscription_service import SubscriptionService


@pytest.fixture
async def setup_entitlement_service(tmp_path):
    db_file = tmp_path / "test_entitlements.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    conn = await init_sqlite_db(db_url)

    user_repo = SqliteUserRepository(conn)
    quota_repo = SqliteDuelQuotaRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    sub_service = SubscriptionService(subscription_repo=sub_repo)
    gaming_service = GamingEntitlementService(
        quota_repo=quota_repo,
        subscription_service=sub_service,
        tz_name="Asia/Kolkata",
    )

    yield {
        "conn": conn,
        "user_repo": user_repo,
        "quota_repo": quota_repo,
        "sub_repo": sub_repo,
        "sub_service": sub_service,
        "gaming_service": gaming_service,
    }
    await conn.close()


@pytest.mark.asyncio
async def test_base_tier_five_duel_limit_and_sixth_rejection(setup_entitlement_service):
    s = setup_entitlement_service
    gaming = s["gaming_service"]
    user_repo = s["user_repo"]

    user_id = "user_base_1"
    partner_id = "partner_unlimited"
    await user_repo.save(User(id=user_id, telegram_id=9001))
    await user_repo.save(User(id=partner_id, telegram_id=9002))

    # User starts on Base tier
    ent = await gaming.get_user_entitlements(user_id)
    assert ent["tier"] == SubscriptionTier.BASE.value
    assert ent["daily_duels_limit"] == 5
    assert ent["daily_duels_used"] == 0
    assert ent["daily_duels_remaining"] == 5

    # Upgrade partner to DIAMOND
    await s["sub_service"].activate_subscription(
        user_id=partner_id,
        new_tier=SubscriptionTier.DIAMOND,
        duration_seconds=30 * 86400,
    )

    # Consume 5 duels consecutively
    for i in range(1, 6):
        can_play, reason, rem = await gaming.can_start_duel(user_id, GameType.CONNECT_FOUR)
        assert can_play is True, f"Failed at duel {i}: {reason}"

        session_id = f"sess_{i}"
        ok, reason = await gaming.consume_duel_credits_for_match(session_id, user_id, partner_id)
        assert ok is True, f"Consume failed at duel {i}: {reason}"

        rem = await gaming.get_daily_duels_remaining(user_id)
        assert rem == 5 - i

    # Verify 5 duels used, 0 remaining
    used = await gaming.get_daily_duels_used(user_id)
    assert used == 5
    rem = await gaming.get_daily_duels_remaining(user_id)
    assert rem == 0

    # 6th duel MUST be rejected
    can_play_6, reason_6, _ = await gaming.can_start_duel(user_id, GameType.CONNECT_FOUR)
    assert can_play_6 is False
    assert "limit" in reason_6.lower()

    # Attempting to consume for the 6th duel fails atomically
    ok_6, reason_consume_6 = await gaming.consume_duel_credits_for_match("sess_6", user_id, partner_id)
    assert ok_6 is False
    assert "limit" in reason_consume_6.lower()


@pytest.mark.asyncio
async def test_subscription_tier_duel_limits(setup_entitlement_service):
    s = setup_entitlement_service
    gaming = s["gaming_service"]
    sub_service = s["sub_service"]
    user_repo = s["user_repo"]

    # Base: 5
    base_user = "user_base_tier"
    await user_repo.save(User(id=base_user, telegram_id=9101))
    assert await gaming.get_daily_duel_limit(base_user) == 5

    # Spark: 10
    spark_user = "user_spark_tier"
    await user_repo.save(User(id=spark_user, telegram_id=9102))
    await sub_service.activate_subscription(
        user_id=spark_user,
        new_tier=SubscriptionTier.SPARK,
        duration_seconds=86400,
    )
    assert await gaming.get_daily_duel_limit(spark_user) == 10

    # Premium: 25
    prem_user = "user_prem_tier"
    await user_repo.save(User(id=prem_user, telegram_id=9103))
    await sub_service.activate_subscription(
        user_id=prem_user,
        new_tier=SubscriptionTier.PREMIUM,
        duration_seconds=30 * 86400,
    )
    assert await gaming.get_daily_duel_limit(prem_user) == 25

    # Diamond: -1 (Unlimited)
    diamond_user = "user_diamond_tier"
    await user_repo.save(User(id=diamond_user, telegram_id=9104))
    await sub_service.activate_subscription(
        user_id=diamond_user,
        new_tier=SubscriptionTier.DIAMOND,
        duration_seconds=30 * 86400,
    )
    assert await gaming.get_daily_duel_limit(diamond_user) == -1
    rem_diamond = await gaming.get_daily_duels_remaining(diamond_user)
    assert rem_diamond == -1


@pytest.mark.asyncio
async def test_solo_games_unlimited_and_zero_duel_quota_consumption(setup_entitlement_service):
    s = setup_entitlement_service
    gaming = s["gaming_service"]
    user_repo = s["user_repo"]
    user_id = "user_solo_lover"
    await user_repo.save(User(id=user_id, telegram_id=9201))

    solo_games = [
        GameType.ZEN_MERGE,
        GameType.WORD_HUNT,
        GameType.COLOR_FLOW,
        GameType.POCKET_GOLF,
        GameType.REFLEX_LAB,
        GameType.DAILY_MYSTERY,
    ]
    for sg in solo_games:
        assert gaming.is_solo_game(sg) is True
        # Solo game is playable even if user has 0 duels or whatever
        can_play, reason, rem = await gaming.can_start_duel(user_id, sg)
        assert can_play is True

    # After checking or starting solo games, daily duels used must remain exactly 0
    used = await gaming.get_daily_duels_used(user_id)
    assert used == 0
    rem = await gaming.get_daily_duels_remaining(user_id)
    assert rem == 5


@pytest.mark.asyncio
async def test_atomic_dual_player_eligibility_and_protection(setup_entitlement_service):
    s = setup_entitlement_service
    gaming = s["gaming_service"]
    user_repo = s["user_repo"]

    user_a = "user_eligible"
    user_b_exhausted = "user_exhausted"
    partner = "dummy_partner"
    await user_repo.save(User(id=user_a, telegram_id=9301))
    await user_repo.save(User(id=user_b_exhausted, telegram_id=9302))
    await user_repo.save(User(id=partner, telegram_id=9303))

    # Exhaust user B's quota (5 duels)
    for i in range(5):
        await gaming.consume_duel_credits_for_match(f"dummy_{i}", user_b_exhausted, partner)

    assert await gaming.get_daily_duels_remaining(user_b_exhausted) == 0
    assert await gaming.get_daily_duels_remaining(user_a) == 5

    # Try to start duel between user A and user B
    ok, reason = await gaming.consume_duel_credits_for_match("match_fail", user_a, user_b_exhausted)
    assert ok is False
    assert "limit" in reason.lower()

    # Crucial guarantee: User A's allowance MUST NOT be deducted when match fails to start!
    assert await gaming.get_daily_duels_remaining(user_a) == 5


@pytest.mark.asyncio
async def test_asia_kolkata_daily_period_calculation(setup_entitlement_service):
    s = setup_entitlement_service
    gaming = s["gaming_service"]

    p_start, p_end, next_reset = gaming.get_current_period_dates()
    assert len(p_start) == 10  # YYYY-MM-DD
    assert len(p_end) == 10
    assert p_start < p_end
    # Ensure next_reset parses as a valid UTC datetime in the future
    dt = datetime.fromisoformat(next_reset)
    assert dt > datetime.now(timezone.utc)
