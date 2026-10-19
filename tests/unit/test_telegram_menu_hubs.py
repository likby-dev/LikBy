"""
tests.unit.test_telegram_menu_hubs
Tests verifying the 5-button main navigation keyboard and inside architecture hubs.
"""

import pytest
from likby.telegram.keyboards import (
    get_chat_hub_keyboard,
    get_connections_hub_keyboard,
    get_main_menu_keyboard,
    get_play_hub_keyboard,
    get_profile_vip_keyboard,
    get_solo_hub_keyboard,
    get_subscription_keyboard,
)


def test_main_menu_keyboard_has_exactly_five_buttons_in_three_rows():
    """Validates the authoritative 5-button layout requested by user."""
    kb = get_main_menu_keyboard()
    rows = kb.keyboard
    assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"

    # Row 1: Hero Matchmaking CTA
    assert len(rows[0]) == 1
    assert rows[0][0].text == "🎲 Find Match"

    # Row 2: Chats & Connections
    assert len(rows[1]) == 2
    assert rows[1][0].text == "💬 My Chats"
    assert rows[1][1].text == "👥 Connections"

    # Row 3: Gaming & Profile Hubs
    assert len(rows[2]) == 2
    assert rows[2][0].text == "🎮 LikBy Play"
    assert rows[2][1].text == "👤 Profile & VIP"

    # Total button count
    total_buttons = sum(len(row) for row in rows)
    assert total_buttons == 5, f"Expected exactly 5 main buttons, found {total_buttons}"


def test_connections_hub_keyboard_structure_and_callbacks():
    """Validates the social and connections inside architecture."""
    kb = get_connections_hub_keyboard(friends_count=2, requests_count=1, likes_count=3)
    rows = kb.inline_keyboard

    # Row 1: Friends and incoming requests with badges
    assert "👥 Friends (2)" in rows[0][0].text
    assert rows[0][0].callback_data == "conn:friends"
    assert "📬 Requests (1)" in rows[0][1].text
    assert rows[0][1].callback_data == "conn:requests"

    # Row 2: Secret admirers (likes) and ID search
    assert "💙 Who Liked Me (3)" in rows[1][0].text
    assert rows[1][0].callback_data == "conn:likes"
    assert "🔍 Search ID" in rows[1][1].text
    assert rows[1][1].callback_data == "conn:search"

    # Row 3: Free Spark referral pass
    assert rows[2][0].callback_data == "sub:invite"


def test_profile_vip_keyboard_structure():
    """Validates the profile, karma, VIP, quotas and safety inside architecture."""
    kb = get_profile_vip_keyboard(tier_code="BASE")
    rows = kb.inline_keyboard

    assert rows[0][0].callback_data == "profile:edit_name"
    assert rows[0][1].callback_data == "vip:karma"

    assert rows[1][0].callback_data == "sub:plans"
    assert rows[1][1].callback_data == "sub:myplan"

    assert rows[2][0].callback_data == "vip:safety"
    assert rows[2][1].callback_data == "sub:paysupport"


def test_chat_hub_keyboard_active_and_idle_states():
    """Validates chat hub controls when in active session vs idle."""
    active_kb = get_chat_hub_keyboard(is_active=True, session_id="ses_12345")
    active_callbacks = [btn.callback_data for row in active_kb.inline_keyboard for btn in row]
    assert "chat:game" in active_callbacks
    assert "chat:next" in active_callbacks
    assert "transcript:export:ses_12345" in active_callbacks
    assert "chat:end" in active_callbacks

    idle_kb = get_chat_hub_keyboard(is_active=False)
    idle_callbacks = [btn.callback_data for row in idle_kb.inline_keyboard for btn in row]
    assert "queue:find_new" in idle_callbacks
    assert "conn:friends" in idle_callbacks
    assert "play:hub" in idle_callbacks


def test_play_and_solo_hub_keyboards_clean_routing():
    """Validates that solo casual games link back to the unified LikBy Play hub."""
    solo_kb = get_solo_hub_keyboard()
    solo_callbacks = [btn.callback_data for row in solo_kb.inline_keyboard for btn in row]
    assert "play:hub" in solo_callbacks
    assert "solo:trivia:new" in solo_callbacks
    assert "solo:gem:new" in solo_callbacks
    assert "solo:rps:new" in solo_callbacks

    play_kb = get_play_hub_keyboard()
    play_callbacks = [btn.callback_data for row in play_kb.inline_keyboard for btn in row]
    assert "play:duels" in play_callbacks
    assert "play:solo_info" in play_callbacks
    assert "play:catalogue" in play_callbacks
    assert "play:progress" in play_callbacks
    assert "sub:plans" in play_callbacks


def test_subscription_keyboard_has_back_to_profile_hub():
    """Validates that subscription view includes back navigation to Profile & VIP hub."""
    sub_kb = get_subscription_keyboard()
    callbacks = [btn.callback_data for row in sub_kb.inline_keyboard for btn in row]
    assert "vip:hub" in callbacks
    assert "sub:buy:SPARK" in callbacks
    assert "sub:buy:PREMIUM" in callbacks
    assert "sub:buy:DIAMOND" in callbacks


def test_interests_keyboard_five_selected_and_markup_extraction():
    """Validates that selecting 5 interests creates Done (5 Selected) and can be extracted."""
    from aiogram.types import Message
    from likby.telegram.keyboards import get_interests_keyboard
    from likby.telegram.handlers.onboarding import extract_selected_interests_from_markup

    selected_5 = ["coffee", "gaming", "tech", "music", "books"]
    kb = get_interests_keyboard(selected=selected_5)

    # Validate Done button text and callback
    done_btn = kb.inline_keyboard[-1][0]
    assert done_btn.text == "✅ Done (5 Selected)"
    assert done_btn.callback_data == "interest_done"

    # Create dummy message with this markup and test extraction
    msg = Message.model_construct(reply_markup=kb)
    extracted = extract_selected_interests_from_markup(msg)
    assert set(extracted) == set(selected_5)
    assert len(extracted) == 5


@pytest.mark.asyncio
async def test_finish_interests_handler_creates_user_and_sends_welcome():
    """Verify that finish_interests processes 5 topics, saves user and profile, and sends welcome."""
    from unittest.mock import AsyncMock, MagicMock
    from aiogram.types import CallbackQuery, Chat, Message, User as TgUser
    from likby.telegram.handlers.onboarding import finish_interests
    from likby.telegram.keyboards import get_interests_keyboard
    from likby.repositories.sqlite.database import init_sqlite_db
    from likby.repositories.sqlite.user_repository import SqliteUserRepository
    from likby.repositories.sqlite.profile_repository import SqliteProfileRepository

    conn = await init_sqlite_db(":memory:")
    u_repo = SqliteUserRepository(conn)
    p_repo = SqliteProfileRepository(conn)

    selected_5 = ["coffee", "gaming", "tech", "music", "books"]
    kb = get_interests_keyboard(selected=selected_5)

    # Mock Telegram types
    tg_user = TgUser(id=12345678, is_bot=False, first_name="Jasvanth", username="jasvanth")
    chat = Chat(id=12345678, type="private")

    msg = MagicMock()
    msg.message_id = 999
    msg.chat = chat
    msg.from_user = tg_user
    msg.reply_markup = kb
    msg.delete = AsyncMock()

    bot_mock = MagicMock()
    bot_mock.send_message = AsyncMock()

    cb = MagicMock()
    cb.id = "cb_test_01"
    cb.from_user = tg_user
    cb.message = msg
    cb.data = "interest_done"
    cb.answer = AsyncMock()
    cb.bot = bot_mock

    # Mock FSM context
    state_mock = MagicMock()
    state_mock.get_data = AsyncMock(return_value={"selected_interests": selected_5, "age": 21, "unique_id": "jasvanth"})
    state_mock.clear = AsyncMock()

    await finish_interests(
        callback=cb,
        state=state_mock,
        user_repo=u_repo,
        profile_repo=p_repo,
        bot=bot_mock,
    )

    # Validate callback acknowledged
    cb.answer.assert_called_once()
    # Validate bot sent welcome message with main menu keyboard
    bot_mock.send_message.assert_called_once()
    send_args = bot_mock.send_message.call_args[1]
    assert send_args["chat_id"] == 12345678
    assert "Profile Created & Safely Saved in Memory!" in send_args["text"]
    assert send_args["reply_markup"] is not None

    # Validate message was deleted
    msg.delete.assert_called_once()

    # Validate user and profile persisted
    saved_user = await u_repo.get_by_telegram_id(12345678)
    assert saved_user is not None
    assert saved_user.unique_id == "jasvanth"
    assert saved_user.state.value == "MAIN_MENU"

    saved_profile = await p_repo.get_by_user_id(saved_user.id)
    assert saved_profile is not None
    assert set(saved_profile.interests) == set(selected_5)
    assert saved_profile.age == 21

    await conn.close()

