"""
likby.domain.entities.profile
User profile domain entity and preference filters.
"""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from likby.domain.enums import Gender, GenderPreference


class Profile(BaseModel):
    """User profile data including demographics, interests, and matching criteria."""

    user_id: str = Field(..., description="Foreign key to User.id")
    unique_id: Optional[str] = Field(default=None, description="Permanent unique user handle (immutable)")
    display_name: str = Field(..., min_length=2, max_length=50, description="Public conversational alias (duplicates allowed)")
    age: int = Field(..., ge=18, le=120, description="User age (must be >= 18)")
    gender: Gender = Field(..., description="Gender identity")
    bio: Optional[str] = Field(default=None, max_length=500, description="Short personal bio")
    location_country: Optional[str] = Field(default=None, max_length=2, description="ISO country code")
    location_city: Optional[str] = Field(default=None, max_length=100, description="City name")
    languages: List[str] = Field(default_factory=lambda: ["en"], description="Spoken languages")
    interests: List[str] = Field(default_factory=list, description="List of topic tags")
    preferred_gender_filter: List[GenderPreference] = Field(
        default_factory=lambda: [GenderPreference.ANY],
        description="Accepted genders for matching",
    )
    min_age_filter: int = Field(default=18, ge=18, description="Minimum partner age")
    max_age_filter: int = Field(default=99, le=120, description="Maximum partner age")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("interests")
    @classmethod
    def normalize_interests(cls, v: List[str]) -> List[str]:
        """Normalize interest tags to lowercase and strip whitespace."""
        normalized = []
        for item in v:
            cleaned = item.strip().lower()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
        return normalized

    @field_validator("max_age_filter")
    @classmethod
    def validate_age_range(cls, v: int, info) -> int:
        min_age = info.data.get("min_age_filter", 18)
        if v < min_age:
            raise ValueError("max_age_filter cannot be less than min_age_filter")
        return v

    def update_display_name(self, new_name: str) -> None:
        """Update public display name (duplicates allowed)."""
        clean_name = new_name.strip()
        if len(clean_name) < 2 or len(clean_name) > 50:
            raise ValueError("Display name must be between 2 and 50 characters.")
        self.display_name = clean_name
        self.updated_at = datetime.now(timezone.utc)
