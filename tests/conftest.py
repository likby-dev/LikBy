"""
tests/conftest.py
Global pytest fixtures and test doubles for Tikible test suites.
"""

import pytest
from tikible.domain.entities.user import User
from tikible.domain.entities.profile import Profile
from tikible.domain.entities.match_ticket import MatchTicket
from tikible.domain.entities.chat_session import ChatSession
from tikible.domain.enums import Gender, GenderPreference, UserState, UserStatus


@pytest.fixture
def sample_user_a() -> User:
    """Active verified test user A."""
    return User(
        id="usr_0001",
        telegram_id=11111111,
        state=UserState.MAIN_MENU,
        status=UserStatus.ACTIVE,
        age_verified=True,
    )


@pytest.fixture
def sample_user_b() -> User:
    """Active verified test user B."""
    return User(
        id="usr_0002",
        telegram_id=22222222,
        state=UserState.MAIN_MENU,
        status=UserStatus.ACTIVE,
        age_verified=True,
    )


@pytest.fixture
def sample_profile_a() -> Profile:
    """Profile for user A."""
    return Profile(
        user_id="usr_0001",
        display_name="Alex",
        age=24,
        gender=Gender.MALE,
        languages=["en"],
        interests=["coding", "gaming", "music"],
        preferred_gender_filter=[GenderPreference.ANY],
        min_age_filter=20,
        max_age_filter=30,
    )


@pytest.fixture
def sample_profile_b() -> Profile:
    """Profile for user B."""
    return Profile(
        user_id="usr_0002",
        display_name="Jordan",
        age=26,
        gender=Gender.FEMALE,
        languages=["en"],
        interests=["gaming", "music", "coffee"],
        preferred_gender_filter=[GenderPreference.ANY],
        min_age_filter=20,
        max_age_filter=30,
    )


@pytest.fixture
def sample_ticket_a(sample_profile_a: Profile) -> MatchTicket:
    """Match ticket for user A."""
    return MatchTicket(
        id="tkt_0001",
        user_id=sample_profile_a.user_id,
        user_gender=sample_profile_a.gender,
        user_age=sample_profile_a.age,
        languages=sample_profile_a.languages,
        interests=sample_profile_a.interests,
        preferred_genders=sample_profile_a.preferred_gender_filter,
        min_age=sample_profile_a.min_age_filter,
        max_age=sample_profile_a.max_age_filter,
    )


@pytest.fixture
def sample_ticket_b(sample_profile_b: Profile) -> MatchTicket:
    """Match ticket for user B."""
    return MatchTicket(
        id="tkt_0002",
        user_id=sample_profile_b.user_id,
        user_gender=sample_profile_b.gender,
        user_age=sample_profile_b.age,
        languages=sample_profile_b.languages,
        interests=sample_profile_b.interests,
        preferred_genders=sample_profile_b.preferred_gender_filter,
        min_age=sample_profile_b.min_age_filter,
        max_age=sample_profile_b.max_age_filter,
    )


@pytest.fixture
def sample_chat_session() -> ChatSession:
    """Active chat session between user A and user B."""
    return ChatSession(
        id="ses_0001",
        user_a_id="usr_0001",
        user_b_id="usr_0002",
        match_score=0.82,
        match_metadata={"common_interests": ["gaming", "music"]},
    )
