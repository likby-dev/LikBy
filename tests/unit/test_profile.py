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


def test_profile_dob_calculation_and_validation():
    from datetime import date
    profile = Profile(
        user_id="usr_001",
        display_name="Sarah",
        age=20,  # Initial placeholder age
        dob=date(2000, 5, 15),
        gender=Gender.FEMALE,
        location_country="United States",
        location_state="California",
        location_city="San Francisco",
        relationship_intent="Friendship",
        languages=["EN", "es", "en"],
    )
    # Exact age calculated from DOB
    assert profile.age >= 23
    assert profile.dob == date(2000, 5, 15)
    assert profile.location_country == "United States"
    assert profile.location_state == "California"
    assert profile.location_city == "San Francisco"
    assert profile.relationship_intent == "Friendship"
    assert profile.languages == ["en", "es"]


def test_profile_dob_underage_rejected():
    from datetime import date, datetime, timezone
    today = datetime.now(timezone.utc).date()
    # 17 years old
    underage_dob = date(today.year - 17, today.month, today.day)
    with pytest.raises(ValidationError):
        Profile(
            user_id="usr_002",
            display_name="Teen",
            age=20,
            dob=underage_dob,
            gender=Gender.FEMALE,
        )


def test_profile_update_methods():
    from datetime import date
    profile = Profile(
        user_id="usr_003",
        display_name="Original",
        age=22,
        gender=Gender.MALE,
    )
    profile.update_display_name("New Name")
    assert profile.display_name == "New Name"

    profile.update_bio("Hello world! Loving music and coding.")
    assert profile.bio == "Hello world! Loving music and coding."

    profile.update_location(country="Germany", state="Bavaria", city="Munich")
    assert profile.location_country == "Germany"
    assert profile.location_state == "Bavaria"
    assert profile.location_city == "Munich"

    profile.update_relationship_intent("Gaming Duo")
    assert profile.relationship_intent == "Gaming Duo"

    profile.update_languages(["EN", "DE", "de"])
    assert profile.languages == ["en", "de"]

    profile.set_dob(date(1998, 10, 10))
    assert profile.dob == date(1998, 10, 10)
    assert profile.age >= 25

