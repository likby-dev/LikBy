"""
tests/unit/test_referral_rewards.py
Unit tests for viral referral invitations, anti-abuse checks, rolling 30-day limits, and earned Spark pass disbursements.
"""

from datetime import datetime, timezone, timedelta
import pytest

from likby.domain.entities.profile import Profile
from likby.domain.entities.user import User
from likby.domain.enums import (
    EntitlementSource,
    Gender,
    GenderPreference,
    ReferralQualificationStatus,
    ReferralRewardStatus,
    SubscriptionTier,
)
from likby.repositories.sqlite.database import init_sqlite_db
from likby.repositories.sqlite.audit_event_repository import SqliteAuditEventRepository
from likby.repositories.sqlite.profile_repository import SqliteProfileRepository
from likby.repositories.sqlite.referral_reward_repository import SqliteReferralRewardRepository
from likby.repositories.sqlite.subscription_repository import SqliteSubscriptionRepository
from likby.repositories.sqlite.user_repository import SqliteUserRepository
from likby.services.audit_service import AuditService
from likby.services.referral_service import ReferralService
from likby.services.subscription_service import SubscriptionService


@pytest.mark.asyncio
async def test_referral_link_generation():
    """Verify unique referral link format."""
    conn = await init_sqlite_db(":memory:")
    user_repo = SqliteUserRepository(conn)
    profile_repo = SqliteProfileRepository(conn)
    referral_repo = SqliteReferralRewardRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    sub_service = SubscriptionService(sub_repo)

    referral_service = ReferralService(
        referral_repo=referral_repo,
        user_repo=user_repo,
        profile_repo=profile_repo,
        subscription_service=sub_service,
        bot_username="LikBy_bot",
    )

    u = User(id="usr_ref_gen", telegram_id=8881, unique_id="coolguy99")
    await user_repo.save(u)

    link = await referral_service.get_user_referral_link("usr_ref_gen")
    assert link == "https://t.me/LikBy_bot?start=ref_coolguy99"

    await conn.close()


@pytest.mark.asyncio
async def test_self_referral_rejected():
    """Verify users cannot refer themselves."""
    conn = await init_sqlite_db(":memory:")
    user_repo = SqliteUserRepository(conn)
    profile_repo = SqliteProfileRepository(conn)
    referral_repo = SqliteReferralRewardRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    sub_service = SubscriptionService(sub_repo)

    referral_service = ReferralService(
        referral_repo=referral_repo,
        user_repo=user_repo,
        profile_repo=profile_repo,
        subscription_service=sub_service,
    )

    u = User(id="usr_self", telegram_id=8882, unique_id="myself")
    await user_repo.save(u)

    ref = await referral_service.record_referral_intent("usr_self", "myself")
    assert ref is None

    await conn.close()


@pytest.mark.asyncio
async def test_qualified_referral_grants_spark_reward():
    """Verify invited user completing profile rewards the referrer with a 24h LikBy Spark pass."""
    conn = await init_sqlite_db(":memory:")
    user_repo = SqliteUserRepository(conn)
    profile_repo = SqliteProfileRepository(conn)
    referral_repo = SqliteReferralRewardRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    audit_repo = SqliteAuditEventRepository(conn)

    sub_service = SubscriptionService(sub_repo)
    audit_service = AuditService(audit_repo)

    referral_service = ReferralService(
        referral_repo=referral_repo,
        user_repo=user_repo,
        profile_repo=profile_repo,
        subscription_service=sub_service,
        audit_service=audit_service,
    )

    # 1. Create Referrer
    referrer = User(id="usr_referrer", telegram_id=1001, unique_id="champion")
    await user_repo.save(referrer)

    # 2. Invited user joins via start payload
    invited = User(id="usr_newbie", telegram_id=1002, age_verified=True)
    await user_repo.save(invited)

    ref = await referral_service.record_referral_intent(invited.id, "champion")
    assert ref is not None
    assert ref.referrer_user_id == referrer.id
    assert ref.qualification_status == ReferralQualificationStatus.PENDING

    # 3. Invited user creates completed profile
    prof = Profile(
        user_id=invited.id,
        display_name="Newbie",
        age=22,
        gender=Gender.MALE,
        interests=["gaming"],
        preferred_gender_filter=[GenderPreference.ANY],
    )
    await profile_repo.save(prof)

    # 4. Trigger qualification evaluation
    reward = await referral_service.evaluate_and_reward_onboarding_completion(invited.id)
    assert reward is not None
    assert reward.qualification_status == ReferralQualificationStatus.QUALIFIED
    assert reward.reward_status in (ReferralRewardStatus.AWARDED, ReferralRewardStatus.REWARDED)

    # 5. Check Referrer has received LikBy Spark entitlement
    referrer_ent = await sub_service.get_user_entitlement(referrer.id)
    assert referrer_ent.tier == SubscriptionTier.SPARK
    assert referrer_ent.source == EntitlementSource.REFERRAL

    await conn.close()


@pytest.mark.asyncio
async def test_rolling_30_day_referral_cap_of_3_spark_passes():
    """Verify referrer can earn a maximum of 3 Spark passes in a rolling 30-day window."""
    conn = await init_sqlite_db(":memory:")
    user_repo = SqliteUserRepository(conn)
    profile_repo = SqliteProfileRepository(conn)
    referral_repo = SqliteReferralRewardRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    audit_repo = SqliteAuditEventRepository(conn)

    sub_service = SubscriptionService(sub_repo)
    audit_service = AuditService(audit_repo)

    referral_service = ReferralService(
        referral_repo=referral_repo,
        user_repo=user_repo,
        profile_repo=profile_repo,
        subscription_service=sub_service,
        audit_service=audit_service,
    )

    referrer = User(id="usr_influencer", telegram_id=7000, unique_id="influencer")
    await user_repo.save(referrer)

    # Qualify 3 referrals -> All 3 rewarded
    for i in range(3):
        invited = User(id=f"usr_fan_{i}", telegram_id=7100 + i, age_verified=True)
        await user_repo.save(invited)
        await referral_service.record_referral_intent(invited.id, "influencer")
        prof = Profile(
            user_id=invited.id,
            display_name=f"Fan {i}",
            age=25,
            gender=Gender.FEMALE,
            interests=["music"],
            preferred_gender_filter=[GenderPreference.ANY],
        )
        await profile_repo.save(prof)
        reward = await referral_service.evaluate_and_reward_onboarding_completion(invited.id)
        assert reward is not None
        assert reward.reward_status in (ReferralRewardStatus.AWARDED, ReferralRewardStatus.REWARDED)

    # 4th referral completes profile -> Qualified, but reward capped
    invited_4 = User(id="usr_fan_4", telegram_id=7104, age_verified=True)
    await user_repo.save(invited_4)
    await referral_service.record_referral_intent(invited_4.id, "influencer")
    prof_4 = Profile(
        user_id=invited_4.id,
        display_name="Fan 4",
        age=25,
        gender=Gender.FEMALE,
        interests=["music"],
        preferred_gender_filter=[GenderPreference.ANY],
    )
    await profile_repo.save(prof_4)
    reward_4 = await referral_service.evaluate_and_reward_onboarding_completion(invited_4.id)
    assert reward_4 is not None
    assert reward_4.qualification_status == ReferralQualificationStatus.QUALIFIED
    assert reward_4.reward_status in (ReferralRewardStatus.CAP_REACHED, ReferralRewardStatus.CAPPED)  # Over 30-day limit

    await conn.close()
