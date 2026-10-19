"""
tests/unit/test_profile_expansion.py
Unit and integration tests for expanded profile details:
- DOB, age derivation, 18+ enforcement
- Bio editing and clearing
- Location (city, state, country) parsing and editing
- Language spoken multi-select toggling
- Relationship / social intent selection
- Partner gender matching filter updates
- Profile Hub rich UI rendering
"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User as TgUser

from likby.domain.entities.profile import Profile
from likby.domain.entities.user import User
from likby.domain.enums import Gender, GenderPreference, UserState, UserStatus
from likby.telegram.handlers.menu import (
    finish_languages,
    finish_profile_interests,
    parse_date_of_birth,
    parse_location_input,
    process_new_bio,
    process_new_dob,
    process_new_location,
    set_preferred_gender,
    set_relationship_intent,
    show_edit_intent,
    show_edit_languages,
    show_edit_pref_gender,
    show_profile_edit_menu,
    show_profile_vip_hub,
    toggle_language,
    toggle_profile_interest,
)
from likby.telegram.states import EditProfileStates


def test_date_of_birth_parser_formats():
    """Verify parse_date_of_birth handles multiple common formats."""
    assert parse_date_of_birth("2000-05-15") == date(2000, 5, 15)
    assert parse_date_of_birth("15/05/2000") == date(2000, 5, 15)
    assert parse_date_of_birth("15-05-2000") == date(2000, 5, 15)
    assert parse_date_of_birth("15.05.2000") == date(2000, 5, 15)
    assert parse_date_of_birth("invalid-date") is None
    assert parse_date_of_birth("") is None


def test_location_parser():
    """Verify parse_location_input handles 1, 2, and 3 comma-separated elements."""
    city, state, country = parse_location_input("San Francisco, California, United States")
    assert city == "San Francisco"
    assert state == "California"
    assert country == "United States"

    city2, state2, country2 = parse_location_input("Paris, France")
    assert city2 == "Paris"
    assert state2 is None
    assert country2 == "France"

    city3, state3, country3 = parse_location_input("Tokyo")
    assert city3 == "Tokyo"
    assert state3 is None
    assert country3 is None

    empty_city, empty_state, empty_country = parse_location_input("")
    assert empty_city is None


@pytest.mark.asyncio
async def test_show_profile_vip_hub_displays_expanded_details():
    """Verify that Profile Hub message includes DOB, Location, Bio, Languages, and Looking For."""
    user = User(
        id="u_hub_test",
        telegram_id=987654321,
        unique_id="alex_star",
        karma_score=350,
    )
    profile = Profile(
        user_id="u_hub_test",
        unique_id="alex_star",
        display_name="Alex Star",
        dob=date(1999, 12, 25),
        age=24,
        gender=Gender.MALE,
        bio="Designing the future of games.",
        location_country="Canada",
        location_state="Ontario",
        location_city="Toronto",
        relationship_intent="Gaming Duo",
        languages=["en", "fr"],
        interests=["gaming", "tech"],
        preferred_gender_filter=[GenderPreference.ANY],
    )

    user_repo_mock = MagicMock()
    user_repo_mock.get_by_telegram_id = AsyncMock(return_value=user)

    profile_repo_mock = MagicMock()
    profile_repo_mock.get_by_user_id = AsyncMock(return_value=profile)

    social_service_mock = MagicMock()
    social_service_mock.get_user_friends = AsyncMock(return_value=[])

    subscription_service_mock = MagicMock()
    subscription_service_mock.get_plan_limits = AsyncMock(return_value={
        "display_name": "Premium",
        "tier": "PREMIUM",
        "max_friends": 15,
        "daily_searches_limit": 100,
        "daily_duel_limit": 25,
    })

    msg = MagicMock(spec=Message)
    msg.from_user = TgUser(id=987654321, is_bot=False, first_name="Alex")
    msg.answer = AsyncMock()

    await show_profile_vip_hub(
        event=msg,
        user_repo=user_repo_mock,
        profile_repo=profile_repo_mock,
        social_service=social_service_mock,
        subscription_service=subscription_service_mock,
    )

    msg.answer.assert_called_once()
    rendered_text = msg.answer.call_args[0][0]
    assert "Alex Star" in rendered_text
    assert "@alex_star" in rendered_text
    assert "25 December 1999" in rendered_text
    assert "Gaming Duo" in rendered_text
    assert "Toronto, Ontario, Canada" in rendered_text
    assert "EN, FR" in rendered_text
    assert "Designing the future of games." in rendered_text
    assert "Elite Match Priority 🌟" in rendered_text


@pytest.mark.asyncio
async def test_process_new_bio_update_and_clear():
    """Verify updating personal bio and clearing it."""
    user = User(id="u_bio_test", telegram_id=121212)
    profile = Profile(
        user_id="u_bio_test",
        display_name="BioUser",
        age=23,
        gender=Gender.FEMALE,
    )

    user_repo_mock = MagicMock()
    user_repo_mock.get_by_telegram_id = AsyncMock(return_value=user)

    profile_repo_mock = MagicMock()
    profile_repo_mock.get_by_user_id = AsyncMock(return_value=profile)
    profile_repo_mock.save = AsyncMock()

    state_mock = MagicMock(spec=FSMContext)
    state_mock.clear = AsyncMock()

    msg = MagicMock(spec=Message)
    msg.from_user = TgUser(id=121212, is_bot=False, first_name="BioUser")
    msg.text = "Coffee lover and night owl."
    msg.answer = AsyncMock()

    # 1. Update bio
    await process_new_bio(msg, state_mock, user_repo_mock, profile_repo_mock)
    assert profile.bio == "Coffee lover and night owl."
    profile_repo_mock.save.assert_called_once()
    state_mock.clear.assert_called_once()
    assert "Bio Updated!" in msg.answer.call_args[0][0]

    # 2. Clear bio
    msg.text = "clear"
    await process_new_bio(msg, state_mock, user_repo_mock, profile_repo_mock)
    assert profile.bio is None


@pytest.mark.asyncio
async def test_process_new_dob_age_calculation_and_restrictions():
    """Verify DOB update calculates age and enforces 18+ requirement."""
    user = User(id="u_dob_test", telegram_id=343434)
    profile = Profile(
        user_id="u_dob_test",
        display_name="DobUser",
        age=20,
        gender=Gender.NON_BINARY,
    )

    user_repo_mock = MagicMock()
    user_repo_mock.get_by_telegram_id = AsyncMock(return_value=user)

    profile_repo_mock = MagicMock()
    profile_repo_mock.get_by_user_id = AsyncMock(return_value=profile)
    profile_repo_mock.save = AsyncMock()

    state_mock = MagicMock(spec=FSMContext)
    state_mock.clear = AsyncMock()

    msg = MagicMock(spec=Message)
    msg.from_user = TgUser(id=343434, is_bot=False, first_name="DobUser")
    msg.answer = AsyncMock()

    # 1. Valid adult DOB
    msg.text = "1995-06-20"
    await process_new_dob(msg, state_mock, user_repo_mock, profile_repo_mock)
    assert profile.dob == date(1995, 6, 20)
    assert profile.age >= 28
    profile_repo_mock.save.assert_called_once()
    assert "Date of Birth Updated!" in msg.answer.call_args[0][0]

    # 2. Underage DOB (16 years old)
    today = datetime.now(timezone.utc).date()
    underage_year = today.year - 16
    msg.text = f"{underage_year}-01-01"
    msg.answer.reset_mock()
    await process_new_dob(msg, state_mock, user_repo_mock, profile_repo_mock)
    assert "Age Restriction" in msg.answer.call_args[0][0]

    # 3. Invalid date format
    msg.text = "not-a-date"
    msg.answer.reset_mock()
    await process_new_dob(msg, state_mock, user_repo_mock, profile_repo_mock)
    assert "Invalid date format" in msg.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_new_location_update():
    """Verify location update parses city, state, country."""
    user = User(id="u_loc_test", telegram_id=565656)
    profile = Profile(
        user_id="u_loc_test",
        display_name="LocUser",
        age=26,
        gender=Gender.FEMALE,
    )

    user_repo_mock = MagicMock()
    user_repo_mock.get_by_telegram_id = AsyncMock(return_value=user)

    profile_repo_mock = MagicMock()
    profile_repo_mock.get_by_user_id = AsyncMock(return_value=profile)
    profile_repo_mock.save = AsyncMock()

    state_mock = MagicMock(spec=FSMContext)
    state_mock.clear = AsyncMock()

    msg = MagicMock(spec=Message)
    msg.from_user = TgUser(id=565656, is_bot=False, first_name="LocUser")
    msg.text = "Austin, Texas, United States"
    msg.answer = AsyncMock()

    await process_new_location(msg, state_mock, user_repo_mock, profile_repo_mock)
    assert profile.location_city == "Austin"
    assert profile.location_state == "Texas"
    assert profile.location_country == "United States"
    profile_repo_mock.save.assert_called_once()
    assert "Location Updated!" in msg.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_relationship_intent_and_preferred_gender_callbacks():
    """Verify inline callbacks for relationship intent and matching preference."""
    user = User(id="u_pref_test", telegram_id=787878)
    profile = Profile(
        user_id="u_pref_test",
        display_name="PrefUser",
        age=22,
        gender=Gender.MALE,
    )

    user_repo_mock = MagicMock()
    user_repo_mock.get_by_telegram_id = AsyncMock(return_value=user)

    profile_repo_mock = MagicMock()
    profile_repo_mock.get_by_user_id = AsyncMock(return_value=profile)
    profile_repo_mock.save = AsyncMock()

    # 1. Update relationship intent
    cb_intent = MagicMock(spec=CallbackQuery)
    cb_intent.data = "intent:Dating & Romance"
    cb_intent.from_user = TgUser(id=787878, is_bot=False, first_name="PrefUser")
    cb_intent.message = MagicMock()
    cb_intent.message.edit_reply_markup = AsyncMock()
    cb_intent.answer = AsyncMock()

    await set_relationship_intent(cb_intent, user_repo_mock, profile_repo_mock)
    assert profile.relationship_intent == "Dating & Romance"
    cb_intent.answer.assert_called_once()

    # 2. Update preferred gender filter
    cb_gender = MagicMock(spec=CallbackQuery)
    cb_gender.data = "pref_gender:FEMALE"
    cb_gender.from_user = TgUser(id=787878, is_bot=False, first_name="PrefUser")
    cb_gender.message = MagicMock()
    cb_gender.message.edit_reply_markup = AsyncMock()
    cb_gender.answer = AsyncMock()

    await set_preferred_gender(cb_gender, user_repo_mock, profile_repo_mock)
    assert profile.preferred_gender_filter == [GenderPreference.FEMALE]
    cb_gender.answer.assert_called_once()


@pytest.mark.asyncio
async def test_language_toggle_and_finish():
    """Verify language toggle and save in profile."""
    user = User(id="u_lang_test", telegram_id=909090)
    profile = Profile(
        user_id="u_lang_test",
        display_name="LangUser",
        age=25,
        gender=Gender.FEMALE,
        languages=["en"],
    )

    user_repo_mock = MagicMock()
    user_repo_mock.get_by_telegram_id = AsyncMock(return_value=user)

    profile_repo_mock = MagicMock()
    profile_repo_mock.get_by_user_id = AsyncMock(return_value=profile)
    profile_repo_mock.save = AsyncMock()

    # Toggle 'es' (Spanish) on
    cb_toggle = MagicMock(spec=CallbackQuery)
    cb_toggle.data = "lang_toggle:es"
    cb_toggle.from_user = TgUser(id=909090, is_bot=False, first_name="LangUser")
    cb_toggle.message = MagicMock()
    cb_toggle.message.edit_reply_markup = AsyncMock()
    cb_toggle.answer = AsyncMock()

    await toggle_language(cb_toggle, user_repo_mock, profile_repo_mock)
    assert "es" in profile.languages
    assert "en" in profile.languages

    # Finish languages
    cb_done = MagicMock(spec=CallbackQuery)
    cb_done.data = "lang_done"
    cb_done.from_user = TgUser(id=909090, is_bot=False, first_name="LangUser")
    cb_done.message = MagicMock()
    cb_done.message.edit_text = AsyncMock()
    cb_done.answer = AsyncMock()

    await finish_languages(cb_done, user_repo_mock, profile_repo_mock)
    cb_done.answer.assert_called_once_with("Languages saved successfully! ✨")
