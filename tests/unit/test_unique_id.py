"""
tests.unit.test_unique_id
Unit tests verifying Unique ID uniqueness rules, format validation, and immutability.
"""

import pytest
from tikible.domain.entities.profile import Profile
from tikible.domain.entities.user import User
from tikible.domain.enums import Gender, GenderPreference
from tikible.telegram.handlers.onboarding import UNIQUE_ID_REGEX


def test_unique_id_regex_validation() -> None:
    """Verify valid and invalid unique ID patterns."""
    valid_ids = ["alex_99", "sam", "cool_tiger_2026", "user123", "a_b_c_1"]
    for uid in valid_ids:
        assert UNIQUE_ID_REGEX.match(uid) is not None, f"Expected {uid} to be valid"

    invalid_ids = [
        "ab",  # too short (<3)
        "this_unique_id_is_way_too_long_for_system",  # too long (>20)
        "alex 99",  # spaces
        "user@name",  # special character @
        "john.doe",  # special character .
        "sam!",  # special character !
        "",  # empty
    ]
    for uid in invalid_ids:
        assert UNIQUE_ID_REGEX.match(uid) is None, f"Expected {uid} to be invalid"


def test_unique_id_immutability_on_user() -> None:
    """Verify user unique_id cannot be edited once set."""
    user = User(id="usr_01", telegram_id=123456)
    assert user.unique_id is None

    # First set succeeds
    user.set_unique_id("alex_99")
    assert user.unique_id == "alex_99"

    # Attempting to edit raises ValueError
    with pytest.raises(ValueError, match="Unique ID is permanent and cannot be modified once set"):
        user.set_unique_id("new_hacker_id")

    # Value remains unchanged
    assert user.unique_id == "alex_99"


def test_duplicate_display_names_allowed_across_profiles() -> None:
    """Verify multiple profiles can share identical display names (Name can be duplicate)."""
    p1 = Profile(
        user_id="usr_01",
        unique_id="alex_99",
        display_name="Alex",
        age=24,
        gender=Gender.MALE,
        interests=["coding", "gaming"],
        preferred_gender_filter=[GenderPreference.ANY],
    )

    p2 = Profile(
        user_id="usr_02",
        unique_id="alex_2026",
        display_name="Alex",  # Duplicate display name
        age=28,
        gender=Gender.FEMALE,
        interests=["music", "books"],
        preferred_gender_filter=[GenderPreference.ANY],
    )

    assert p1.display_name == p2.display_name == "Alex"
    assert p1.unique_id != p2.unique_id


def test_display_name_can_be_edited_on_profile() -> None:
    """Verify display name can be edited while unique_id remains unchanged."""
    profile = Profile(
        user_id="usr_01",
        unique_id="shadow_walker",
        display_name="Original Name",
        age=25,
        gender=Gender.NON_BINARY,
        interests=["art", "movies"],
    )

    profile.update_display_name("Updated Cool Name")
    assert profile.display_name == "Updated Cool Name"
    assert profile.unique_id == "shadow_walker"
