"""
likby.services.gaming_entitlement_service
Centralized subscription-aware daily duel allowance and solo gaming quota service.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple
import uuid
from zoneinfo import ZoneInfo

from likby.domain.entities.play_game import GAME_CATALOGUE, DuelQuotaUsage
from likby.domain.enums import GameMode, GameType, SubscriptionTier
from likby.repositories.interfaces import DuelQuotaRepository
from likby.services.subscription_service import SubscriptionService


UNLIMITED_DUELS = -1  # Explicit representation of unlimited allowance

TIER_DUEL_ALLOWANCES: Dict[SubscriptionTier, int] = {
    SubscriptionTier.BASE: 5,
    SubscriptionTier.SPARK: 10,
    SubscriptionTier.PREMIUM: 25,
    SubscriptionTier.DIAMOND: UNLIMITED_DUELS,
}


class GamingEntitlementService:
    """
    Centralized server-side entitlement service for LikBy Play.
    Enforces daily duel limits per subscription tier with Asia/Kolkata boundary.
    Solo games are strictly unlimited for every tier and never consume duel credits.
    """

    def __init__(
        self,
        quota_repo: DuelQuotaRepository,
        subscription_service: SubscriptionService,
        tz_name: str = "Asia/Kolkata",
    ) -> None:
        self._quota_repo = quota_repo
        self._sub_service = subscription_service
        try:
            self._tz = ZoneInfo(tz_name)
        except Exception:
            self._tz = timezone.utc

    def get_current_period_dates(self) -> Tuple[str, str, str]:
        """
        Calculates (period_start, period_end, next_reset_iso) in configured product timezone (Asia/Kolkata).
        """
        now = datetime.now(self._tz)
        today_str = now.strftime("%Y-%m-%d")
        tomorrow = now.date() + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")

        # Midnight next day in local timezone
        next_reset_dt = datetime(
            year=tomorrow.year,
            month=tomorrow.month,
            day=tomorrow.day,
            hour=0,
            minute=0,
            second=0,
            tzinfo=self._tz,
        )
        return today_str, tomorrow_str, next_reset_dt.astimezone(timezone.utc).isoformat()

    def is_solo_game(self, game_id: GameType) -> bool:
        """Determines whether a game is a solo experience (always unlimited)."""
        defn = GAME_CATALOGUE.get(game_id)
        if not defn:
            return False
        return defn.mode == GameMode.SOLO

    async def get_daily_duel_limit(self, user_id: str) -> int:
        """
        Resolve authoritative daily duel allowance.
        Returns:
            5 for LIKBY_BASE
            10 for LIKBY_SPARK
            25 for LIKBY_PREMIUM
            -1 for LIKBY_DIAMOND (unlimited)
        """
        entitlement = await self._sub_service.get_user_entitlement(user_id)
        tier = entitlement.tier
        return TIER_DUEL_ALLOWANCES.get(tier, 5)

    async def get_daily_duels_used(self, user_id: str) -> int:
        """Calculate already-consumed duels in today's Asia/Kolkata quota period."""
        period_start, _, _ = self.get_current_period_dates()
        return await self._quota_repo.count_duels_in_period(user_id, period_start)

    async def get_daily_duels_remaining(self, user_id: str) -> int:
        """Calculate remaining duels for today. Returns -1 if unlimited."""
        limit = await self.get_daily_duel_limit(user_id)
        if limit == UNLIMITED_DUELS:
            return UNLIMITED_DUELS
        used = await self.get_daily_duels_used(user_id)
        return max(0, limit - used)

    async def can_start_duel(self, user_id: str, game_id: Optional[GameType] = None) -> Tuple[bool, str, int]:
        """
        Check whether user has quota to start a duel.
        Solo games bypass duel checks immediately.
        Returns: (is_allowed, failure_reason, remaining_allowance)
        """
        if game_id and self.is_solo_game(game_id):
            return True, "Solo games are unlimited for all tiers.", UNLIMITED_DUELS

        limit = await self.get_daily_duel_limit(user_id)
        if limit == UNLIMITED_DUELS:
            return True, "LikBy Diamond includes unlimited daily duels.", UNLIMITED_DUELS

        used = await self.get_daily_duels_used(user_id)
        remaining = max(0, limit - used)
        if remaining <= 0:
            return (
                False,
                f"You have reached today's limit of {limit} duels. Solo games are still unlimited, or upgrade your plan for more duels.",
                0,
            )
        return True, "Eligible to start duel.", remaining

    async def get_user_entitlements(self, user_id: str) -> Dict[str, Any]:
        """Comprehensive game entitlement summary for lobby and /mygames."""
        entitlement = await self._sub_service.get_user_entitlement(user_id)
        tier = entitlement.tier
        limit = TIER_DUEL_ALLOWANCES.get(tier, 5)
        used = await self.get_daily_duels_used(user_id)
        remaining = UNLIMITED_DUELS if limit == UNLIMITED_DUELS else max(0, limit - used)
        _, _, next_reset_iso = self.get_current_period_dates()

        return {
            "user_id": user_id,
            "tier": tier.value,
            "tier_display_name": f"LikBy {tier.value.capitalize()}",
            "daily_duel_limit": limit,
            "daily_duels_limit": limit,
            "duels_used_today": used,
            "daily_duels_used": used,
            "duels_remaining_today": remaining,
            "daily_duels_remaining": remaining,
            "is_unlimited": limit == UNLIMITED_DUELS,
            "solo_games_unlimited": True,
            "next_reset_at": next_reset_iso,
        }

    async def consume_duel_credits_for_match(
        self,
        session_id: str,
        user_a_id: str,
        user_b_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Atomic duel credit consumption from BOTH participants.
        Both users must have remaining quota before either deduction is committed.
        If either participant lacks quota, no credit is consumed and game session cannot start.
        """
        key_base = idempotency_key or f"duel_{session_id}_{uuid.uuid4().hex[:8]}"

        # 1. Verify User A
        ok_a, reason_a, _ = await self.can_start_duel(user_a_id)
        if not ok_a:
            return False, f"Host cannot start duel: {reason_a}"

        # 2. Verify User B
        ok_b, reason_b, _ = await self.can_start_duel(user_b_id)
        if not ok_b:
            return False, f"Challenger cannot start duel: {reason_b}"

        # 3. Check if already consumed for this session
        has_a = await self._quota_repo.has_consumed_for_session(user_a_id, session_id)
        has_b = await self._quota_repo.has_consumed_for_session(user_b_id, session_id)
        if has_a and has_b:
            return True, "Credits already consumed for this duel session."

        period_start, period_end, _ = self.get_current_period_dates()
        now = datetime.now(timezone.utc)

        ent_a = await self._sub_service.get_user_entitlement(user_a_id)
        ent_b = await self._sub_service.get_user_entitlement(user_b_id)

        # 4. Record consumption for User A
        if not has_a:
            usage_a = DuelQuotaUsage(
                id=f"dqu_{uuid.uuid4().hex[:14]}",
                user_id=user_a_id,
                game_session_id=session_id,
                subscription_tier_snapshot=ent_a.tier,
                quota_period_start=period_start,
                quota_period_end=period_end,
                consumed_at=now,
                idempotency_key=f"{key_base}_a",
            )
            saved_a = await self._quota_repo.record_consumption(usage_a)
            if not saved_a:
                return False, "Failed to reserve host duel credit."

        # 5. Record consumption for User B
        if not has_b:
            usage_b = DuelQuotaUsage(
                id=f"dqu_{uuid.uuid4().hex[:14]}",
                user_id=user_b_id,
                game_session_id=session_id,
                subscription_tier_snapshot=ent_b.tier,
                quota_period_start=period_start,
                quota_period_end=period_end,
                consumed_at=now,
                idempotency_key=f"{key_base}_b",
            )
            saved_b = await self._quota_repo.record_consumption(usage_b)
            if not saved_b:
                return False, "Failed to reserve challenger duel credit."

        return True, "Duel credits successfully reserved for both participants."
