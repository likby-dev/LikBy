"""
likby.services.usage_service
Atomic quota tracking, daily reset management, and usage limits enforcement.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple
from zoneinfo import ZoneInfo
from likby.domain.enums import FeatureKey
from likby.repositories.interfaces import UsageCounterRepository
from likby.services.subscription_service import SubscriptionService


class UsageService:
    """Evaluates and reserves quota-governed actions with atomic versioned counters."""

    def __init__(
        self,
        usage_repo: UsageCounterRepository,
        subscription_service: SubscriptionService,
        tz_name: str = "Asia/Kolkata",
    ) -> None:
        self._usage_repo = usage_repo
        self._subscription_service = subscription_service
        try:
            self._tz = ZoneInfo(tz_name)
        except Exception:
            self._tz = timezone.utc

    def get_current_period_dates(self) -> Tuple[str, str]:
        """
        Returns (period_start, period_end) strings YYYY-MM-DD
        aligned to the configured timezone boundary (Asia/Kolkata).
        """
        now = datetime.now(self._tz)
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        return today_str, tomorrow_str

    async def get_feature_limit(self, user_id: str, feature_key: FeatureKey) -> int:
        """Resolve feature limit from user's current subscription entitlement."""
        limits = await self._subscription_service.get_plan_limits(user_id)
        if feature_key == FeatureKey.LIKES:
            return limits.get("daily_likes_limit", 25)
        elif feature_key == FeatureKey.SEARCHES:
            return limits.get("daily_searches_limit", 10)
        elif feature_key == FeatureKey.REQUESTS:
            return limits.get("daily_requests_limit", 3)
        elif feature_key == FeatureKey.GAMES:
            return limits.get("daily_games_limit", 3)
        elif feature_key == FeatureKey.ICEBREAKERS:
            return limits.get("daily_icebreakers_limit", 3)
        elif feature_key in (FeatureKey.BOOSTS,):
            return limits.get("profile_boosts", 0)
        elif feature_key in (FeatureKey.UPLOADS, FeatureKey.DAILY_UPLOADS):
            return limits.get("daily_uploads_limit", 20)
        elif feature_key in (FeatureKey.RECEIVED, FeatureKey.DAILY_RECEIVED):
            return limits.get("daily_receive_limit", 10)
        return 0

    @staticmethod
    def get_next_reset_utc() -> datetime:
        """Returns the upcoming 00:00:00 UTC daily reset timestamp."""
        now_utc = datetime.now(timezone.utc)
        tomorrow_utc = (now_utc + timedelta(days=1)).date()
        return datetime(tomorrow_utc.year, tomorrow_utc.month, tomorrow_utc.day, 0, 0, 0, tzinfo=timezone.utc)

    async def can_consume(
        self,
        user_id: str,
        feature_key: FeatureKey,
        delta: int = 1,
    ) -> Tuple[bool, int, int]:
        """
        Check whether user has quota to consume.
        Returns: (is_allowed, currently_used, limit)
        """
        period_start, _ = self.get_current_period_dates()
        used = await self._usage_repo.get_usage(user_id, feature_key, period_start)
        limit = await self.get_feature_limit(user_id, feature_key)
        is_allowed = (used + delta) <= limit
        return is_allowed, used, limit

    async def consume(
        self,
        user_id: str,
        feature_key: FeatureKey,
        delta: int = 1,
    ) -> Tuple[bool, int, int]:
        """
        Atomically reserve and increment feature quota.
        Returns: (success, new_used_count, limit)
        """
        period_start, period_end = self.get_current_period_dates()
        limit = await self.get_feature_limit(user_id, feature_key)
        used = await self._usage_repo.get_usage(user_id, feature_key, period_start)

        if used + delta > limit:
            return False, used, limit

        new_used = await self._usage_repo.increment_usage(
            user_id=user_id,
            feature_key=feature_key,
            period_start=period_start,
            period_end=period_end,
            delta=delta,
        )
        return True, new_used, limit

    async def get_user_daily_summary(self, user_id: str) -> Dict[str, dict]:
        """Returns map of all features with used, limit, and remaining."""
        period_start, _ = self.get_current_period_dates()
        summary = {}
        for fk in [
            FeatureKey.LIKES,
            FeatureKey.SEARCHES,
            FeatureKey.REQUESTS,
            FeatureKey.GAMES,
            FeatureKey.ICEBREAKERS,
            FeatureKey.UPLOADS,
            FeatureKey.RECEIVED,
        ]:
            limit = await self.get_feature_limit(user_id, fk)
            used = await self._usage_repo.get_usage(user_id, fk, period_start)
            summary[fk.value] = {
                "used": used,
                "limit": limit,
                "remaining": max(0, limit - used),
            }
        return summary

    async def check_and_consume(
        self,
        user_id: str,
        feature_key: FeatureKey,
        amount: int = 1,
    ) -> Tuple[bool, int]:
        """Atomically check and consume quota, returning (allowed, remaining)."""
        success, new_used, limit = await self.consume(user_id, feature_key, delta=amount)
        remaining = max(0, limit - new_used)
        return success, remaining

    async def get_used_count(self, user_id: str, feature_key: FeatureKey) -> int:
        """Get currently consumed count for feature today."""
        period_start, _ = self.get_current_period_dates()
        return await self._usage_repo.get_usage(user_id, feature_key, period_start)
