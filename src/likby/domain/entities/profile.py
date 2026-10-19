"""
likby.domain.entities.profile
User profile domain entity and preference filters.
"""

from datetime import date, datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from likby.domain.enums import Gender, GenderPreference


class Profile(BaseModel):
    """User profile data including demographics, interests, and matching criteria."""

    user_id: str = Field(..., description="Foreign key to User.id")
    unique_id: Optional[str] = Field(default=None, description="Permanent unique user handle (immutable)")
    display_name: str = Field(..., min_length=2, max_length=50, description="Public conversational alias (duplicates allowed)")
    dob: Optional[date] = Field(default=None, description="Date of birth (YYYY-MM-DD)")
    age: int = Field(..., ge=18, le=120, description="User age (must be >= 18)")
    gender: Gender = Field(..., description="Gender identity")
    bio: Optional[str] = Field(default=None, max_length=500, description="Short personal bio")
    location_country: Optional[str] = Field(default=None, max_length=60, description="Country name or ISO code")
    location_state: Optional[str] = Field(default=None, max_length=100, description="State / Province")
    location_city: Optional[str] = Field(default=None, max_length=100, description="City name")
    relationship_intent: Optional[str] = Field(default=None, max_length=50, description="Social or relationship intent")
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

    @field_validator("languages")
    @classmethod
    def normalize_languages(cls, v: List[str]) -> List[str]:
        """Normalize language codes/names to lowercase and ensure non-empty."""
        normalized = []
        for item in v:
            cleaned = item.strip().lower()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
        return normalized or ["en"]

    @field_validator("max_age_filter")
    @classmethod
    def validate_age_range(cls, v: int, info) -> int:
        min_age = info.data.get("min_age_filter", 18)
        if v < min_age:
            raise ValueError("max_age_filter cannot be less than min_age_filter")
        return v

    @model_validator(mode="after")
    def validate_dob_and_age(self) -> "Profile":
        """If dob is provided, verify it aligns with age >= 18 and recalculate exact age."""
        if self.dob is not None:
            today = datetime.now(timezone.utc).date()
            if self.dob > today:
                raise ValueError("Date of birth cannot be in the future.")
            calc_age = today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
            if calc_age < 18:
                raise ValueError(f"User must be at least 18 years old (calculated age: {calc_age}).")
            if calc_age > 120:
                raise ValueError("Date of birth indicates age exceeding 120 years.")
            self.age = calc_age
        return self

    def update_display_name(self, new_name: str) -> None:
        """Update public display name (duplicates allowed)."""
        clean_name = new_name.strip()
        if len(clean_name) < 2 or len(clean_name) > 50:
            raise ValueError("Display name must be between 2 and 50 characters.")
        self.display_name = clean_name
        self.updated_at = datetime.now(timezone.utc)

    def set_dob(self, new_dob: date) -> None:
        """Set date of birth and derive verified age."""
        today = datetime.now(timezone.utc).date()
        if new_dob > today:
            raise ValueError("Date of birth cannot be in the future.")
        calc_age = today.year - new_dob.year - ((today.month, today.day) < (new_dob.month, new_dob.day))
        if calc_age < 18:
            raise ValueError(f"Must be at least 18 years old (calculated age: {calc_age}).")
        if calc_age > 120:
            raise ValueError("Date of birth indicates age exceeding 120 years.")
        self.dob = new_dob
        self.age = calc_age
        self.updated_at = datetime.now(timezone.utc)

    def update_bio(self, new_bio: Optional[str]) -> None:
        """Update bio text."""
        clean_bio = new_bio.strip() if new_bio else None
        if clean_bio and len(clean_bio) > 500:
            raise ValueError("Bio cannot exceed 500 characters.")
        self.bio = clean_bio or None
        self.updated_at = datetime.now(timezone.utc)

    def update_location(
        self,
        country: Optional[str] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
    ) -> None:
        """Update geographic location."""
        self.location_country = country.strip()[:60] if country and country.strip() else None
        self.location_state = state.strip()[:100] if state and state.strip() else None
        self.location_city = city.strip()[:100] if city and city.strip() else None
        self.updated_at = datetime.now(timezone.utc)

    def update_languages(self, langs: List[str]) -> None:
        """Update spoken languages."""
        normalized = []
        for lang in langs:
            cleaned = lang.strip().lower()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
        self.languages = normalized or ["en"]
        self.updated_at = datetime.now(timezone.utc)

    def update_gender(self, new_gender: Gender) -> None:
        """Update gender identity."""
        self.gender = new_gender
        self.updated_at = datetime.now(timezone.utc)

    def update_preferences(
        self,
        preferred_gender: Optional[List[GenderPreference]] = None,
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
    ) -> None:
        """Update partner matching preferences."""
        if preferred_gender is not None:
            self.preferred_gender_filter = preferred_gender
        if min_age is not None:
            if min_age < 18:
                raise ValueError("min_age_filter cannot be less than 18")
            self.min_age_filter = min_age
        if max_age is not None:
            if max_age > 120:
                raise ValueError("max_age_filter cannot exceed 120")
            if max_age < self.min_age_filter:
                raise ValueError("max_age_filter cannot be less than min_age_filter")
            self.max_age_filter = max_age
        self.updated_at = datetime.now(timezone.utc)

    def update_relationship_intent(self, intent: Optional[str]) -> None:
        """Update relationship / social intent."""
        clean_intent = intent.strip() if intent else None
        if clean_intent and len(clean_intent) > 50:
            raise ValueError("Relationship intent cannot exceed 50 characters.")
        self.relationship_intent = clean_intent or None
        self.updated_at = datetime.now(timezone.utc)

