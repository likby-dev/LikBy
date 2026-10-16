"""
likby.domain.entities.subscription
Centralized subscription entitlement model and tier limits.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from likby.domain.enums import SubscriptionTier


PLAN_LIMITS = {
    SubscriptionTier.FREE: {
        "max_friends": 3,
        "daily_searches_limit": 3,
        "daily_requests_limit": 5,
    },
    SubscriptionTier.PREMIUM: {
        "max_friends": 10,
        "daily_searches_limit": 20,
        "daily_requests_limit": 25,
    },
    SubscriptionTier.HIGHER: {
        "max_friends": 25,
        "daily_searches_limit": 100,
        "daily_requests_limit": 100,
    },
}


class SubscriptionEntitlement(BaseModel):
    """Centralized subscription standing and evaluated feature limits."""

    user_id: str = Field(..., description="Foreign key to User.id")
    tier: SubscriptionTier = Field(default=SubscriptionTier.FREE, description="Active subscription tier")
    max_friends: int = Field(default=3, description="Maximum concurrent friends allowed")
    daily_searches_limit: int = Field(default=3, description="Allowed ID searches per day")
    daily_requests_limit: int = Field(default=5, description="Allowed connection requests per day")
    starts_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    is_active: bool = Field(default=True)

    @classmethod
    def create_default_free(cls, user_id: str) -> "SubscriptionEntitlement":
        """Instantiate standard free tier entitlement."""
        limits = PLAN_LIMITS[SubscriptionTier.FREE]
        return cls(
            user_id=user_id,
            tier=SubscriptionTier.FREE,
            max_friends=limits["max_friends"],
            daily_searches_limit=limits["daily_searches_limit"],
            daily_requests_limit=limits["daily_requests_limit"],
            starts_at=datetime.now(timezone.utc),
            expires_at=None,
            is_active=True,
        )

    def upgrade_to(self, new_tier: SubscriptionTier, expires_at: Optional[datetime] = None) -> None:
        """Upgrade entitlement to higher plan tier."""
        limits = PLAN_LIMITS[new_tier]
        self.tier = new_tier
        self.max_friends = limits["max_friends"]
        self.daily_searches_limit = limits["daily_searches_limit"]
        self.daily_requests_limit = limits["daily_requests_limit"]
        self.expires_at = expires_at
        self.is_active = True
