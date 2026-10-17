"""
likby.services.subscription_service
Centralized subscription catalog, entitlement evaluation, upgrades, and automated expiry reconciliation.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from likby.domain.entities.subscription import (
    PLAN_LIMITS,
    PLAN_SPECS,
    SubscriptionEntitlement,
)
from likby.domain.enums import EntitlementSource, EntitlementStatus, SubscriptionTier
from likby.repositories.interfaces import SubscriptionRepository
from likby.services.audit_service import AuditService


class SubscriptionService:
    """Manages subscription tiers, feature gates, usage limits, and entitlement state transitions."""

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._repo = subscription_repo
        self._audit = audit_service

    async def get_or_create_entitlement(self, user_id: str) -> SubscriptionEntitlement:
        """
        Retrieve current subscription entitlement or initialize default LikBy Base tier.
        Evaluates expiration synchronously on access for zero-timer resilience.
        """
        ent = await self._repo.get_by_user_id(user_id)
        now = datetime.now(timezone.utc)

        if ent:
            # Handle automatic expiration / downgrade to LikBy Base
            if ent.expires_at and ent.expires_at < now and ent.tier != SubscriptionTier.BASE:
                previous_tier = ent.tier.value
                ent.upgrade_to(SubscriptionTier.BASE, expires_at=None, source=EntitlementSource.FREE)
                await self._repo.save(ent)

                if self._audit:
                    await self._audit.record(
                        actor_id="SYSTEM",
                        event_type="SUBSCRIPTION_EXPIRED_DOWNGRADED",
                        entity_type="SUBSCRIPTION",
                        entity_id=user_id,
                        metadata={
                            "previous_tier": previous_tier,
                            "new_tier": SubscriptionTier.BASE.value,
                            "expired_at": now.isoformat(),
                        },
                    )
            return ent

        # Create default LikBy Base tier
        default_ent = SubscriptionEntitlement.create_default_free(user_id)
        await self._repo.save(default_ent)

        if self._audit:
            await self._audit.record(
                actor_id=user_id,
                event_type="SUBSCRIPTION_INITIALIZED_BASE",
                entity_type="SUBSCRIPTION",
                entity_id=user_id,
                metadata={"tier": SubscriptionTier.BASE.value},
            )

        return default_ent

    async def activate_subscription(
        self,
        user_id: str,
        new_tier: SubscriptionTier,
        duration_seconds: int,
        source: EntitlementSource = EntitlementSource.PURCHASE,
        source_transaction_id: Optional[str] = None,
    ) -> SubscriptionEntitlement:
        """
        Activates or extends a paid/earned entitlement without discarding unused time.
        """
        ent = await self.get_or_create_entitlement(user_id)
        now = datetime.now(timezone.utc)

        # Calculate new expiry
        if ent.tier == new_tier and ent.expires_at and ent.expires_at > now:
            # Repeat purchase of same tier: extend existing active time
            new_expiry = ent.expires_at + timedelta(seconds=duration_seconds)
            action = "SUBSCRIPTION_EXTENDED"
        else:
            # New tier / Upgrade
            new_expiry = now + timedelta(seconds=duration_seconds)
            action = "SUBSCRIPTION_ACTIVATED"

        ent.upgrade_to(
            new_tier=new_tier,
            expires_at=new_expiry,
            source=source,
            source_transaction_id=source_transaction_id,
        )
        await self._repo.save(ent)

        if self._audit:
            await self._audit.record(
                actor_id=user_id,
                event_type=action,
                entity_type="SUBSCRIPTION",
                entity_id=user_id,
                metadata={
                    "tier": new_tier.value,
                    "duration_seconds": duration_seconds,
                    "source": source.value,
                    "source_transaction_id": source_transaction_id,
                    "expires_at": new_expiry.isoformat(),
                },
            )

        return ent

    async def upgrade_tier(
        self,
        user_id: str,
        new_tier: SubscriptionTier,
        duration_days: int = 30,
    ) -> SubscriptionEntitlement:
        """Backwards compatibility helper for existing callers."""
        duration_seconds = duration_days * 86400
        return await self.activate_subscription(
            user_id=user_id,
            new_tier=new_tier,
            duration_seconds=duration_seconds,
            source=EntitlementSource.PURCHASE,
        )

    async def can_add_friend(self, user_id: str, current_friend_count: int) -> bool:
        """
        Check whether the user has capacity to add another friend.
        Friends survive downgrade: existing friends are never deleted, but new friends require capacity.
        """
        ent = await self.get_or_create_entitlement(user_id)
        return current_friend_count < ent.max_friends

    get_user_entitlement = get_or_create_entitlement

    def get_tier_spec(self, tier: SubscriptionTier) -> Dict[str, Any]:
        """Return authoritative plan specification for tier."""
        return PLAN_SPECS.get(tier, PLAN_SPECS[SubscriptionTier.BASE])

    async def get_plan_limits(self, user_id: str) -> Dict[str, Any]:
        """Get evaluated feature limits for a user."""
        ent = await self.get_or_create_entitlement(user_id)
        spec = PLAN_SPECS.get(ent.tier, PLAN_SPECS[SubscriptionTier.BASE])

        return {
            "tier": ent.tier.value,
            "display_name": spec["display_name"],
            "max_friends": ent.max_friends,
            "daily_likes_limit": ent.daily_likes_limit,
            "daily_searches_limit": ent.daily_searches_limit,
            "daily_requests_limit": ent.daily_requests_limit,
            "daily_games_limit": ent.daily_games_limit,
            "daily_icebreakers_limit": ent.daily_icebreakers_limit,
            "pending_requests_limit": ent.pending_requests_limit,
            "profile_boosts": ent.profile_boosts_remaining,
            "priority_support": spec.get("priority_support", False),
            "daily_uploads_limit": ent.daily_uploads_limit,
            "daily_receive_limit": ent.daily_receive_limit,
            "max_image_size_bytes": getattr(ent, "max_image_size_bytes", spec.get("max_image_size_bytes", 20971520)),
            "max_video_size_bytes": getattr(ent, "max_video_size_bytes", spec.get("max_video_size_bytes", 20971520)),
            "starts_at": ent.starts_at.isoformat(),
            "expires_at": ent.expires_at.isoformat() if ent.expires_at else None,
            "is_active": ent.is_active,
        }

    async def activate_entitlement(
        self,
        user_id: str,
        tier: SubscriptionTier,
        source: EntitlementSource = EntitlementSource.PURCHASE,
        duration_days: int = 30,
        source_transaction_id: Optional[str] = None,
    ) -> SubscriptionEntitlement:
        """Convenience method to activate entitlement with duration in days."""
        return await self.activate_subscription(
            user_id=user_id,
            new_tier=tier,
            duration_seconds=duration_days * 86400,
            source=source,
            source_transaction_id=source_transaction_id,
        )
