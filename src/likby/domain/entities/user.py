"""
likby.domain.entities.user
User domain entity and business lifecycle methods.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from likby.domain.enums import UserState, UserStatus


class User(BaseModel):
    """User account entity representing a registered individual."""

    id: str = Field(..., description="Unique internal user identifier (UUID or usr_...)")
    telegram_id: int = Field(..., description="Telegram user ID")
    unique_id: Optional[str] = Field(default=None, description="User-defined permanent unique handle (immutable)")
    state: UserState = Field(default=UserState.ONBOARDING_AGE_GATE, description="Conversational state")
    status: UserStatus = Field(default=UserStatus.ACTIVE, description="Account standing")
    age_verified: bool = Field(default=False, description="Whether 18+ gate was passed")
    terms_accepted_at: Optional[datetime] = None
    karma_score: int = Field(default=100, description="Behavioral reputation score")
    report_count: int = Field(default=0, description="Total reports received")
    ban_reason: Optional[str] = None
    banned_at: Optional[datetime] = None
    last_active_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def set_unique_id(self, unique_id: str) -> None:
        """Set the permanent unique ID. Cannot be modified once set."""
        if self.unique_id is not None:
            raise ValueError("Unique ID is permanent and cannot be modified once set.")
        self.unique_id = unique_id.strip().lower()
        self.updated_at = datetime.now(timezone.utc)

    def verify_age(self) -> None:
        """Pass the 18+ age verification gate."""
        self.age_verified = True
        self.terms_accepted_at = datetime.now(timezone.utc)
        self.state = UserState.ONBOARDING_ALIAS
        self.updated_at = datetime.now(timezone.utc)

    def transition_state(self, new_state: UserState) -> None:
        """Transition user conversational state."""
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)

    def touch_activity(self) -> None:
        """Update last active timestamp."""
        now = datetime.now(timezone.utc)
        self.last_active_at = now
        self.updated_at = now

    def apply_report_penalty(self) -> None:
        """Deduct karma and increment report counter."""
        self.report_count += 1
        self.karma_score = max(0, self.karma_score - 15)
        self.updated_at = datetime.now(timezone.utc)
        if self.report_count >= 3:
            self.status = UserStatus.SUSPENDED

    def ban(self, reason: str) -> None:
        """Administrative ban of the user."""
        self.status = UserStatus.BANNED
        self.ban_reason = reason
        self.banned_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    @property
    def is_eligible_for_matching(self) -> bool:
        """Check if user can search for conversation partners."""
        return (
            self.status == UserStatus.ACTIVE
            and self.age_verified
            and self.state == UserState.MAIN_MENU
            and self.karma_score >= 20
        )
