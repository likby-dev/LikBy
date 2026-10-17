"""
likby.domain.entities.referral
Entities representing invitations, referral qualification, and earned reward passes.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from likby.domain.enums import ReferralQualificationStatus, ReferralRewardStatus


class ReferralReward(BaseModel):
    """Immutable invitation and earned Spark pass reward record."""

    id: str = Field(..., description="Referral ID e.g. ref_01K8...")
    referrer_user_id: str = Field(..., description="Foreign key to User.id of the inviter")
    invited_user_id: str = Field(..., description="Foreign key to User.id of the invited user")
    qualification_status: ReferralQualificationStatus = Field(default=ReferralQualificationStatus.PENDING)
    reward_status: ReferralRewardStatus = Field(default=ReferralRewardStatus.PENDING)
    reward_entitlement_id: Optional[str] = Field(default=None, description="Foreign key to SubscriptionEntitlement.id if rewarded")
    qualified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
