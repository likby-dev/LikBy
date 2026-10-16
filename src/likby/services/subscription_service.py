"""
likby.services.subscription_service
Centralized subscription and entitlement evaluation service.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from likby.domain.entities.subscription import SubscriptionEntitlement, PLAN_LIMITS
from likby.domain.enums import SubscriptionTier
from likby.repositories.interfaces import SubscriptionRepository


class SubscriptionService:
    """Manages subscription tiers, feature gates, and usage limits."""

    def __init__(self, subscription_repo: SubscriptionRepository) -> None:
        self._repo = subscription_repo

    async def get_or_create_entitlement(self, user_id: str) -> SubscriptionEntitlement:
        """Retrieve current subscription entitlement or initialize default Free tier."""
        ent = await self._repo.get_by_user_id(user_id)
        now = datetime.now(timezone.utc)

        if ent:
            # Handle automatic expiration/downgrade check
            if ent.expires_at and ent.expires_at < now and ent.tier != SubscriptionTier.FREE:
                ent.upgrade_to(SubscriptionTier.FREE, expires_at=None)
                await self._repo.save(ent)
            return ent

        # Create default Free tier
        default_ent = SubscriptionEntitlement.create_default_free(user_id)
        await self._repo.save(default_ent)
        return default_ent

    async def upgrade_tier(
        self,
        user_id: str,
        new_tier: SubscriptionTier,
        duration_days: int = 30,
    ) -> SubscriptionEntitlement:
        """Upgrade user to a target subscription tier with expiration."""
        ent = await self.get_or_create_entitlement(user_id)
        expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)
        ent.upgrade_to(new_tier, expires_at=expires_at)
        await self._repo.save(ent)
        return ent

    async def can_add_friend(self, user_id: str, current_friend_count: int) -> bool:
        """Check whether the user has capacity to add another friend."""
        ent = await self.get_or_create_entitlement(user_id)
        return current_friend_count < ent.max_friends

    async def get_plan_limits(self, user_id: str) -> dict:
        """Get evaluated feature limits for a user."""
        ent = await self.get_or_create_entitlement(user_id)
        return {
            "tier": ent.tier.value,
            "max_friends": ent.max_friends,
            "daily_searches_limit": ent.daily_searches_limit,
            "daily_requests_limit": ent.daily_requests_limit,
            "expires_at": ent.expires_at.isoformat() if ent.expires_at else None,
            "is_active": ent.is_active,
        }
