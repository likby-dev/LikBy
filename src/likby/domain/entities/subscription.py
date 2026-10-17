"""
likby.domain.entities.subscription
Centralized subscription catalog, provider pricing, entitlement model, and tier limits.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from likby.domain.enums import (
    EntitlementSource,
    EntitlementStatus,
    PaymentProviderType,
    SubscriptionTier,
)


# Authoritative Subscription Plan Specifications
PLAN_SPECS: Dict[SubscriptionTier, Dict[str, Any]] = {
    SubscriptionTier.BASE: {
        "code": "BASE",
        "name": "LikBy Base",
        "display_name": "LikBy Base",
        "target_price_inr_paise": 0,
        "stars_amount": 0,
        "prices": {"INR": 0, "XTR": 0},
        "duration_seconds": None,  # Lifetime / No expiry
        "duration_days": None,
        "max_friends": 3,
        "daily_likes_limit": 25,
        "daily_searches_limit": 10,
        "daily_requests_limit": 3,
        "pending_requests_limit": 10,
        "daily_games_limit": 3,
        "daily_icebreakers_limit": 3,
        "daily_uploads_limit": 20,
        "daily_receive_limit": 10,
        "max_image_size_bytes": 20971520,
        "max_video_size_bytes": 20971520,
        "profile_boosts": 0,
        "priority_support": False,
        "limits": {
            "likes_per_day": 25,
            "id_lookups_per_day": 10,
            "direct_requests_per_day": 3,
            "pending_outgoing_requests": 10,
            "games_started_per_day": 3,
            "active_friends_capacity": 3,
            "daily_likes_limit": 25,
            "daily_searches_limit": 10,
            "daily_requests_limit": 3,
            "pending_requests_limit": 10,
            "daily_games_limit": 3,
            "daily_uploads_limit": 20,
            "daily_receive_limit": 10,
            "max_friends": 3,
        },
        "description": "Essential anonymous discovery and chat with fundamental community limits.",
    },
    SubscriptionTier.SPARK: {
        "code": "SPARK",
        "name": "LikBy Spark",
        "display_name": "LikBy Spark",
        "target_price_inr_paise": 1900,  # ₹19
        "stars_amount": 15,  # 15 Stars
        "prices": {"INR": 1900, "XTR": 15},
        "duration_seconds": 86400,  # 24 Hours
        "duration_days": 1,
        "max_friends": 5,
        "daily_likes_limit": 50,
        "daily_searches_limit": 25,
        "daily_requests_limit": 5,
        "pending_requests_limit": 15,
        "daily_games_limit": 10,
        "daily_icebreakers_limit": 10,
        "daily_uploads_limit": 40,
        "daily_receive_limit": 20,
        "max_image_size_bytes": 20971520,
        "max_video_size_bytes": 20971520,
        "profile_boosts": 1,
        "priority_support": False,
        "limits": {
            "likes_per_day": 50,
            "id_lookups_per_day": 25,
            "direct_requests_per_day": 5,
            "pending_outgoing_requests": 15,
            "games_started_per_day": 10,
            "active_friends_capacity": 5,
            "daily_likes_limit": 50,
            "daily_searches_limit": 25,
            "daily_requests_limit": 5,
            "pending_requests_limit": 15,
            "daily_games_limit": 10,
            "daily_uploads_limit": 40,
            "daily_receive_limit": 20,
            "max_friends": 5,
        },
        "description": "24-Hour accelerator pass for social surges, extra discovery, and match boost.",
    },
    SubscriptionTier.PREMIUM: {
        "code": "PREMIUM",
        "name": "LikBy Premium",
        "display_name": "LikBy Premium",
        "target_price_inr_paise": 7900,  # ₹79
        "stars_amount": 60,  # 60 Stars
        "prices": {"INR": 7900, "XTR": 60},
        "duration_seconds": 2592000,  # 30 Days
        "duration_days": 30,
        "optional_90d_inr_paise": 19900,  # ₹199
        "optional_90d_stars": 150,
        "max_friends": 15,
        "daily_likes_limit": 100,
        "daily_searches_limit": 100,
        "daily_requests_limit": 15,
        "pending_requests_limit": 30,
        "daily_games_limit": 25,
        "daily_icebreakers_limit": 30,
        "daily_uploads_limit": 100,
        "daily_receive_limit": 50,
        "max_image_size_bytes": 52428800,  # 50 MB
        "max_video_size_bytes": 52428800,
        "profile_boosts": 2,
        "priority_support": False,
        "limits": {
            "likes_per_day": 100,
            "id_lookups_per_day": 100,
            "direct_requests_per_day": 15,
            "pending_outgoing_requests": 30,
            "games_started_per_day": 25,
            "active_friends_capacity": 15,
            "daily_likes_limit": 100,
            "daily_searches_limit": 100,
            "daily_requests_limit": 15,
            "pending_requests_limit": 30,
            "daily_games_limit": 25,
            "daily_uploads_limit": 100,
            "daily_receive_limit": 50,
            "max_friends": 15,
        },
        "description": "Full monthly social experience with expanded friend lists and frequent matching.",
    },
    SubscriptionTier.DIAMOND: {
        "code": "DIAMOND",
        "name": "LikBy Diamond",
        "display_name": "LikBy Diamond",
        "target_price_inr_paise": 14900,  # ₹149
        "stars_amount": 120,  # 120 Stars
        "prices": {"INR": 14900, "XTR": 120},
        "duration_seconds": 2592000,  # 30 Days
        "duration_days": 30,
        "optional_90d_inr_paise": 39900,  # ₹399
        "optional_90d_stars": 300,
        "max_friends": 50,
        "daily_likes_limit": 200,
        "daily_searches_limit": 250,
        "daily_requests_limit": 30,
        "pending_requests_limit": 60,
        "daily_games_limit": 50,
        "daily_icebreakers_limit": 100,
        "daily_uploads_limit": 250,
        "daily_receive_limit": 100,
        "max_image_size_bytes": 104857600,  # 100 MB
        "max_video_size_bytes": 104857600,
        "profile_boosts": 4,
        "priority_support": True,
        "limits": {
            "likes_per_day": 200,
            "id_lookups_per_day": 250,
            "direct_requests_per_day": 30,
            "pending_outgoing_requests": 60,
            "games_started_per_day": 50,
            "active_friends_capacity": 50,
            "daily_likes_limit": 200,
            "daily_searches_limit": 250,
            "daily_requests_limit": 30,
            "pending_requests_limit": 60,
            "daily_games_limit": 50,
            "daily_uploads_limit": 250,
            "daily_receive_limit": 100,
            "max_friends": 50,
        },
        "description": "VIP access with maximum limits, priority support queue, and elite matching capabilities.",
    },
}

# Backward compatibility plan limits map
PLAN_LIMITS: Dict[SubscriptionTier, Dict[str, Any]] = {
    tier: {
        "max_friends": spec["max_friends"],
        "daily_searches_limit": spec["daily_searches_limit"],
        "daily_requests_limit": spec["daily_requests_limit"],
        "daily_likes_limit": spec["daily_likes_limit"],
        "daily_games_limit": spec["daily_games_limit"],
        "daily_icebreakers_limit": spec["daily_icebreakers_limit"],
        "daily_uploads_limit": spec.get("daily_uploads_limit", 20),
        "daily_receive_limit": spec.get("daily_receive_limit", 10),
        "max_image_size_bytes": spec.get("max_image_size_bytes", 20971520),
        "max_video_size_bytes": spec.get("max_video_size_bytes", 20971520),
        "pending_requests_limit": spec["pending_requests_limit"],
        "profile_boosts": spec["profile_boosts"],
    }
    for tier, spec in PLAN_SPECS.items()
}


class SubscriptionPlan(BaseModel):
    """Database representation of an authoritative subscription plan."""

    id: str = Field(..., description="Unique plan ID e.g. plan_base")
    code: str = Field(..., description="Machine-readable code: BASE, SPARK, PREMIUM, DIAMOND")
    display_name: str = Field(..., description="Official brand name e.g. LikBy Base")
    active: bool = Field(default=True)
    entitlements_json: Dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProviderPrice(BaseModel):
    """Provider-specific purchasable pricing definition."""

    id: str = Field(..., description="Price ID e.g. prc_spark_stars")
    plan_id: str = Field(..., description="Foreign key to SubscriptionPlan.id")
    provider: PaymentProviderType
    provider_product_id: Optional[str] = None
    amount_minor_units: int = Field(..., description="Paise for INR, integer count for XTR")
    currency: str = Field(..., description="INR or XTR")
    duration_seconds: int = Field(..., description="Period duration in seconds")
    active: bool = Field(default=True)
    environment: str = Field(default="production")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SubscriptionEntitlement(BaseModel):
    """Centralized subscription standing and evaluated feature limits."""

    id: Optional[str] = None
    user_id: str = Field(..., description="Foreign key to User.id")
    tier: SubscriptionTier = Field(default=SubscriptionTier.BASE, description="Active subscription tier")
    max_friends: int = Field(default=3, description="Maximum concurrent friends allowed")
    daily_likes_limit: int = Field(default=25, description="Allowed session likes per day")
    daily_searches_limit: int = Field(default=10, description="Allowed ID searches per day")
    daily_requests_limit: int = Field(default=3, description="Allowed connection requests per day")
    daily_games_limit: int = Field(default=3, description="Allowed games started per day")
    daily_icebreakers_limit: int = Field(default=3, description="Allowed AI icebreakers per day")
    daily_uploads_limit: int = Field(default=20, description="Allowed media items uploaded per day")
    daily_receive_limit: int = Field(default=10, description="Allowed media items received per day")
    max_image_size_bytes: int = Field(default=20971520, description="Max image file size bytes")
    max_video_size_bytes: int = Field(default=20971520, description="Max video file size bytes")
    pending_requests_limit: int = Field(default=10, description="Max pending outgoing requests")
    profile_boosts_remaining: int = Field(default=0, description="Available profile boost tokens")
    source: EntitlementSource = Field(default=EntitlementSource.FREE)
    source_transaction_id: Optional[str] = None
    status: EntitlementStatus = Field(default=EntitlementStatus.ACTIVE)
    starts_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create_default_free(cls, user_id: str) -> "SubscriptionEntitlement":
        """Instantiate standard free Base tier entitlement."""
        spec = PLAN_SPECS[SubscriptionTier.BASE]
        return cls(
            id=f"ent_base_{user_id}",
            user_id=user_id,
            tier=SubscriptionTier.BASE,
            max_friends=spec["max_friends"],
            daily_likes_limit=spec["daily_likes_limit"],
            daily_searches_limit=spec["daily_searches_limit"],
            daily_requests_limit=spec["daily_requests_limit"],
            daily_games_limit=spec["daily_games_limit"],
            daily_icebreakers_limit=spec["daily_icebreakers_limit"],
            daily_uploads_limit=spec.get("daily_uploads_limit", 20),
            daily_receive_limit=spec.get("daily_receive_limit", 10),
            max_image_size_bytes=spec.get("max_image_size_bytes", 20971520),
            max_video_size_bytes=spec.get("max_video_size_bytes", 20971520),
            pending_requests_limit=spec["pending_requests_limit"],
            profile_boosts_remaining=spec["profile_boosts"],
            source=EntitlementSource.FREE,
            status=EntitlementStatus.ACTIVE,
            starts_at=datetime.now(timezone.utc),
            expires_at=None,
            is_active=True,
        )

    def upgrade_to(
        self,
        new_tier: SubscriptionTier,
        expires_at: Optional[datetime] = None,
        source: EntitlementSource = EntitlementSource.PURCHASE,
        source_transaction_id: Optional[str] = None,
    ) -> None:
        """Upgrade entitlement to target plan tier."""
        spec = PLAN_SPECS[new_tier]
        self.tier = new_tier
        self.max_friends = spec["max_friends"]
        self.daily_likes_limit = spec["daily_likes_limit"]
        self.daily_searches_limit = spec["daily_searches_limit"]
        self.daily_requests_limit = spec["daily_requests_limit"]
        self.daily_games_limit = spec["daily_games_limit"]
        self.daily_icebreakers_limit = spec["daily_icebreakers_limit"]
        self.daily_uploads_limit = spec.get("daily_uploads_limit", 20)
        self.daily_receive_limit = spec.get("daily_receive_limit", 10)
        self.max_image_size_bytes = spec.get("max_image_size_bytes", 20971520)
        self.max_video_size_bytes = spec.get("max_video_size_bytes", 20971520)
        self.pending_requests_limit = spec["pending_requests_limit"]
        self.profile_boosts_remaining += spec["profile_boosts"]
        self.expires_at = expires_at
        self.source = source
        self.source_transaction_id = source_transaction_id
        self.status = EntitlementStatus.ACTIVE
        self.is_active = True
        self.updated_at = datetime.now(timezone.utc)

