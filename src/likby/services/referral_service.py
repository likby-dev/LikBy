"""
likby.services.referral_service
Qualified referral program and earned LikBy Spark passes lifecycle.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
import uuid
from likby.domain.entities.referral import ReferralReward
from likby.domain.enums import (
    EntitlementSource,
    ReferralQualificationStatus,
    ReferralRewardStatus,
    SubscriptionTier,
)
from likby.repositories.interfaces import (
    ProfileRepository,
    ReferralRewardRepository,
    UserRepository,
)
from likby.services.audit_service import AuditService
from likby.services.subscription_service import SubscriptionService


class ReferralService:
    """Manages viral referral links, anti-abuse checks, and earned Spark pass disbursements."""

    MAX_REWARDS_PER_30_DAYS = 3
    REWARD_DURATION_SECONDS = 86400  # 24 Hours

    def __init__(
        self,
        referral_repo: ReferralRewardRepository,
        user_repo: UserRepository,
        profile_repo: ProfileRepository,
        subscription_service: SubscriptionService,
        audit_service: Optional[AuditService] = None,
        bot_username: str = "LikBy_bot",
    ) -> None:
        self._referral_repo = referral_repo
        self._user_repo = user_repo
        self._profile_repo = profile_repo
        self._subscription_service = subscription_service
        self._audit = audit_service
        self._bot_username = bot_username

    def generate_referral_link(self, referrer_unique_id: str) -> str:
        """Construct standard Telegram referral deep-link."""
        return f"https://t.me/{self._bot_username}?start=ref_{referrer_unique_id}"

    async def register_referral_intent(
        self,
        referrer_unique_id: str,
        invited_user_id: str,
    ) -> Tuple[bool, str, Optional[ReferralReward]]:
        """
        Record that a newly onboarded user arrived via a referrer's unique invite code.
        """
        referrer = await self._user_repo.get_by_unique_id(referrer_unique_id)
        if not referrer:
            return False, "Invalid referral code.", None

        if referrer.id == invited_user_id:
            return False, "Self-referral is not permitted.", None

        # Check if this invited user was already referred
        existing = await self._referral_repo.get_by_invited_user_id(invited_user_id)
        if existing:
            return False, "User was already referred previously.", existing

        ref_reward = ReferralReward(
            id=f"ref_{uuid.uuid4().hex[:12]}",
            referrer_user_id=referrer.id,
            invited_user_id=invited_user_id,
            qualification_status=ReferralQualificationStatus.PENDING,
            reward_status=ReferralRewardStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        await self._referral_repo.save(ref_reward)

        if self._audit:
            await self._audit.record(
                actor_id=invited_user_id,
                event_type="REFERRAL_INTENT_RECORDED",
                entity_type="REFERRAL",
                entity_id=ref_reward.id,
                metadata={
                    "referrer_user_id": referrer.id,
                    "invited_user_id": invited_user_id,
                },
            )

        return True, "Referral intent registered successfully.", ref_reward

    async def evaluate_and_grant_reward(
        self,
        invited_user_id: str,
    ) -> Tuple[bool, str]:
        """
        Evaluate if invited user satisfies qualification rules (age verified & completed profile)
        and disburse earned 24h LikBy Spark pass to referrer (subject to 30-day cap).
        """
        record = await self._referral_repo.get_by_invited_user_id(invited_user_id)
        if not record or record.qualification_status == ReferralQualificationStatus.QUALIFIED:
            return False, "No pending referral found or already qualified."

        # Verify invited user meets minimum quality rules
        user = await self._user_repo.get_by_id(invited_user_id)
        if not user or not user.age_verified:
            return False, "User has not verified age."

        profile = await self._profile_repo.get_by_user_id(invited_user_id)
        if not profile or not profile.display_name or not profile.interests:
            return False, "User profile is incomplete."

        # Mark qualified
        now = datetime.now(timezone.utc)
        record.qualification_status = ReferralQualificationStatus.QUALIFIED
        record.qualified_at = now

        # Enforce rolling 30-day cap (maximum 3 rewards)
        thirty_days_ago = (now - timedelta(days=30)).isoformat()
        recent_count = await self._referral_repo.count_qualified_in_period(
            record.referrer_user_id, since=thirty_days_ago
        )

        if recent_count >= self.MAX_REWARDS_PER_30_DAYS:
            record.reward_status = ReferralRewardStatus.CAP_REACHED
            await self._referral_repo.save(record)
            return False, "Referrer reached 30-day reward cap (3 passes maximum)."

        # Disburse earned LikBy Spark pass (24 Hours)
        ent = await self._subscription_service.activate_subscription(
            user_id=record.referrer_user_id,
            new_tier=SubscriptionTier.SPARK,
            duration_seconds=self.REWARD_DURATION_SECONDS,
            source=EntitlementSource.REFERRAL,
        )

        record.reward_status = ReferralRewardStatus.REWARDED
        record.reward_entitlement_id = ent.id or f"ent_spark_{record.referrer_user_id}"
        await self._referral_repo.save(record)

        if self._audit:
            await self._audit.record(
                actor_id="SYSTEM",
                event_type="REFERRAL_REWARD_GRANTED",
                entity_type="REFERRAL",
                entity_id=record.id,
                metadata={
                    "referrer_user_id": record.referrer_user_id,
                    "invited_user_id": invited_user_id,
                    "tier_granted": SubscriptionTier.SPARK.value,
                    "duration_seconds": self.REWARD_DURATION_SECONDS,
                },
            )

        return True, "Referral qualified and 24h LikBy Spark pass granted to referrer."

    async def get_referrer_stats(self, referrer_user_id: str) -> dict:
        """Returns referral counts and reward limits for /invite."""
        referrals = await self._referral_repo.get_user_referrals(referrer_user_id)
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        recent_rewards = await self._referral_repo.count_qualified_in_period(
            referrer_user_id, since=thirty_days_ago
        )

        total_invites = len(referrals)
        qualified_invites = sum(1 for r in referrals if r.qualification_status == ReferralQualificationStatus.QUALIFIED)

        return {
            "total_invites": total_invites,
            "qualified_invites": qualified_invites,
            "recent_rewards_30d": recent_rewards,
            "max_rewards_30d": self.MAX_REWARDS_PER_30_DAYS,
            "remaining_reward_slots": max(0, self.MAX_REWARDS_PER_30_DAYS - recent_rewards),
        }

    async def get_user_referral_link(self, user_id: str) -> str:
        """Construct user's referral link using unique_id if present."""
        user = await self._user_repo.get_by_id(user_id)
        code = user.unique_id if user and user.unique_id else user_id
        return self.generate_referral_link(code)

    async def record_referral_intent(
        self,
        invited_user_id: str,
        referrer_unique_id: str,
    ) -> Optional[ReferralReward]:
        """Record referral intent and return ReferralReward on success."""
        ok, msg, reward = await self.register_referral_intent(
            referrer_unique_id=referrer_unique_id,
            invited_user_id=invited_user_id,
        )
        return reward if ok else None

    async def evaluate_and_reward_onboarding_completion(
        self,
        invited_user_id: str,
    ) -> Optional[ReferralReward]:
        """Evaluate onboarding qualification and return updated reward record."""
        ok, msg = await self.evaluate_and_grant_reward(invited_user_id)
        return await self._referral_repo.get_by_invited_user_id(invited_user_id)
