"""
tests/unit/test_profile.py
Unit tests for Profile entity, validation, and interest normalization.
"""

import pytest
from pydantic import ValidationError
from likby.domain.entities.profile import Profile
from likby.domain.enums import Gender, GenderPreference


def test_profile_creation_and_normalization():
    profile = Profile(
        user_id="usr_001",
        display_name="Alex",
        age=25,
        gender=Gender.NON_BINARY,
        interests=["  Coding ", "GAMING", "coding", "Music"],
        preferred_gender_filter=[GenderPreference.ANY],
        min_age_filter=21,
        max_age_filter=35,
    )
    # Deduplicated, trimmed, lowercased
    assert profile.interests == ["coding", "gaming", "music"]
    assert profile.age == 25
    assert profile.display_name == "Alex"


def test_profile_underage_rejected():
    with pytest.raises(ValidationError):
        Profile(
            user_id="usr_001",
            display_name="Youngster",
            age=17,  # Less than 18
            gender=Gender.MALE,
        )


def test_profile_invalid_age_filter_range():
    with pytest.raises(ValidationError):
        Profile(
            user_id="usr_001",
            display_name="Alex",
            age=25,
            gender=Gender.MALE,
            min_age_filter=30,
            max_age_filter=20,  # Max less than min
        )
