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

    play_kb = get_play_hub_keyboard("https://likby-dev.onrender.com/play/")
    play_callbacks = [btn.callback_data for row in play_kb.inline_keyboard for btn in row]
    assert "play:duels" in play_callbacks
    assert "play:solo_info" in play_callbacks
    assert "play:catalogue" in play_callbacks
    assert "play:progress" in play_callbacks
    assert "sub:plans" in play_callbacks

    # Verify no open mini button at top, and no count numbers in any button labels
    all_texts = [btn.text for row in play_kb.inline_keyboard for btn in row]
    assert not any("Open LikBy Play" in t for t in all_texts)
    assert not any("(11 Games)" in t or "(6 Games)" in t or "17 Games" in t for t in all_texts)
    assert "⚔️ 2-Player Duels" in all_texts
    assert "🧩 Solo Games" in all_texts
    assert "✨ Games Catalog & Rules" in all_texts


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


def test_solo_games_keyboards_https_and_fallback():
    """Validates that solo games keyboard uses WebApp when https is available, and fallback otherwise."""
    from likby.telegram.keyboards import get_solo_games_keyboard, get_solo_game_card_keyboard

    # Local / non-https -> fallback to callback_data
    kb_local = get_solo_games_keyboard("http://localhost:8000/play/")
    for row in kb_local.inline_keyboard[:3]:
        for btn in row:
            assert btn.callback_data.startswith("play:solo_card:")
            assert btn.web_app is None

    # Production https -> direct 1-tap WebApp
    kb_prod = get_solo_games_keyboard("https://likby-dev.onrender.com/play/")
    for row in kb_prod.inline_keyboard[:3]:
        for btn in row:
            assert btn.web_app is not None
            assert "game=" in btn.web_app.url

    card_kb = get_solo_game_card_keyboard("zen_merge", "https://likby-dev.onrender.com/play/")
    assert card_kb.inline_keyboard[0][0].web_app is not None
    assert "game=zen_merge" in card_kb.inline_keyboard[0][0].web_app.url


@pytest.mark.asyncio
async def test_solo_number_shortcut_typing_one_when_idle():
    """Validates that typing '1' outside an active session displays the Zen Merge game card."""
    from unittest.mock import AsyncMock, MagicMock
    from aiogram.types import Message, User
    from likby.telegram.handlers.play import handle_solo_number_shortcut

    msg = MagicMock(spec=Message)
    msg.text = "1"
    msg.from_user = User(id=99999, is_bot=False, first_name="Jasvanth")
    msg.answer = AsyncMock()

    relay_mock = MagicMock()
    relay_mock.get_or_warm_session = AsyncMock(return_value=None)

    await handle_solo_number_shortcut(msg, chat_relay=relay_mock)

    msg.answer.assert_called_once()
    call_args = msg.answer.call_args[0]
    assert "Zen Merge" in call_args[0]
    assert "Solo Game #1" in call_args[0]


@pytest.mark.asyncio
async def test_chat_message_unrelayed_solo_shortcut_and_idle_help():
    """Validates that unrelayed chat messages cleanly launch solo games or give friendly idle guidance."""
    from unittest.mock import AsyncMock, MagicMock
    from aiogram.types import Message, User
    from likby.telegram.handlers.chat import handle_chat_message

    user_repo_mock = MagicMock()
    chat_relay_mock = MagicMock()
    chat_relay_mock.relay_text = AsyncMock(return_value=False)

    # 1. User types '1' when not in active chat
    msg1 = MagicMock(spec=Message)
    msg1.text = "1"
    msg1.from_user = User(id=88888, is_bot=False, first_name="Alex")
    msg1.answer = AsyncMock()

    await handle_chat_message(msg1, user_repo=user_repo_mock, chat_relay=chat_relay_mock)
    msg1.answer.assert_called_once()
    assert "Zen Merge" in msg1.answer.call_args[0][0]

    # 2. User types normal text 'hello' when not in active chat
    msg2 = MagicMock(spec=Message)
    msg2.text = "hello"
    msg2.from_user = User(id=88888, is_bot=False, first_name="Alex")
    msg2.answer = AsyncMock()

    await handle_chat_message(msg2, user_repo=user_repo_mock, chat_relay=chat_relay_mock)
    msg2.answer.assert_called_once()
    text_sent = msg2.answer.call_args[0][0]
    assert "You are not currently in an active chat session" in text_sent
    assert "Free Solo Games" in text_sent


def test_duel_games_keyboards_all_twelve_buttons():
    """Validates that duel games keyboard provides all 12 games as selectable buttons with session validation."""
    from likby.telegram.keyboards import get_duel_games_keyboard, get_duel_game_card_keyboard

    # Local / non-https -> callbacks
    kb_local = get_duel_games_keyboard("http://localhost:8000/play/")
    game_callbacks = [btn.callback_data for row in kb_local.inline_keyboard[:6] for btn in row]
    assert len(game_callbacks) == 12
    assert "play:duel_select:connect_four" in game_callbacks
    assert "play:duel_select:carrom_clash" in game_callbacks
    assert "play:duel_select:air_rush" in game_callbacks
    assert "play:duel_select:pocket_pool" in game_callbacks
    assert "play:duel_select:stick_arena" in game_callbacks
    assert "play:duel_select:quickdraw" in game_callbacks
    assert "play:duel_select:word_rush" in game_callbacks
    assert "play:duel_select:brain_blitz" in game_callbacks
    assert "play:duel_select:reflex_rush" in game_callbacks
    assert "play:duel_select:mindmatch" in game_callbacks
    assert "play:duel_select:mystery_mission" in game_callbacks
    assert "play:duel_select:xo" in game_callbacks

    # Verify solo and open mini app buttons are removed from duels keyboard
    all_callbacks = [btn.callback_data for row in kb_local.inline_keyboard for btn in row if btn.callback_data]
    assert "play:solo_info" not in all_callbacks
    assert "play:hub" in all_callbacks

    # HTTPS Mini App keyboard also uses session-gated callbacks instead of un-gated mini app bypass
    kb_https = get_duel_games_keyboard("https://likby.onrender.com/play/")
    https_callbacks = [btn.callback_data for row in kb_https.inline_keyboard[:6] for btn in row]
    assert len(https_callbacks) == 12
    assert "play:duel_select:xo" in https_callbacks

    # Card keyboard provides challenge action
    card_kb = get_duel_game_card_keyboard("carrom_clash", in_active_session=True)
    assert card_kb.inline_keyboard[0][0].callback_data == "play:duel_select:carrom_clash"


@pytest.mark.asyncio
async def test_show_duels_handler_presents_button_selector():
    """Validates that show_duels handler renders all 12 duels as clickable buttons."""
    from unittest.mock import AsyncMock, MagicMock
    from aiogram.types import CallbackQuery, Message, User
    from likby.telegram.handlers.play import show_duels

    cb = MagicMock(spec=CallbackQuery)
    cb.data = "play:duels"
    cb.from_user = User(id=77777, is_bot=False, first_name="Player")
    cb.answer = AsyncMock()
    msg = MagicMock(spec=Message)
    msg.edit_text = AsyncMock()
    cb.message = msg

    user_repo_mock = MagicMock()
    user_repo_mock.get_by_telegram_id = AsyncMock(return_value=None)

    await show_duels(cb, user_repo=user_repo_mock)

    cb.answer.assert_called_once()
    msg.edit_text.assert_called_once()
    kwargs = msg.edit_text.call_args[1]
    markup = kwargs["reply_markup"]
    assert markup is not None
    callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data]
    assert "play:duel_select:connect_four" in callbacks
    assert "play:duel_select:carrom_clash" in callbacks
    assert "play:duel_select:xo" in callbacks


@pytest.mark.asyncio
async def test_duel_select_when_idle_shows_active_session_required_notification():
    """Validates that selecting a duel game without an active session alerts that an active session is needed."""
    from unittest.mock import AsyncMock, MagicMock
    from aiogram.types import CallbackQuery, Message, User
    from likby.telegram.handlers.play import duel_game_select_callback

    cb = MagicMock(spec=CallbackQuery)
    cb.data = "play:duel_select:connect_four"
    cb.from_user = User(id=11111, is_bot=False, first_name="IdlePlayer")
    cb.answer = AsyncMock()
    msg = MagicMock(spec=Message)
    msg.edit_text = AsyncMock()
    cb.message = msg

    relay_mock = MagicMock()
    relay_mock.get_or_warm_session = AsyncMock(return_value=None)
    user_repo_mock = MagicMock()

    await duel_game_select_callback(
        cb,
        user_repo=user_repo_mock,
        chat_relay=relay_mock,
    )

    cb.answer.assert_called_once()
    assert "Multiplayer Duel games require an active conversation session" in cb.answer.call_args[0][0]
    msg.edit_text.assert_called_once()
    text_sent = msg.edit_text.call_args[0][0]
    assert "Active Session Required for Duels" in text_sent
    assert "Connect Four" in text_sent

    # Verify buttons to find match and solo games
    markup = msg.edit_text.call_args[1]["reply_markup"]
    cbs = [b.callback_data for r in markup.inline_keyboard for b in r if b.callback_data]
    assert "queue:find_new" in cbs
    assert "play:solo_info" in cbs


@pytest.mark.asyncio
async def test_duel_challenge_flow_and_mutual_entry_with_quota_decrement():
    """Validates duel invite, accept, -1 credit deduction, and mutual Mini App launch."""
    from unittest.mock import AsyncMock, MagicMock
    from aiogram import Bot
    from aiogram.types import CallbackQuery, Message, User
    from likby.domain.entities.play_game import GameInvitation, PlayGameSession
    from likby.domain.enums import GameInvitationStatus, GameMode, GameType, PlaySessionStatus
    from likby.services.session_cache import CachedSession
    from likby.telegram.handlers.play import duel_game_select_callback, duel_accept_callback
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    cached = CachedSession(
        session_id="ses_abc123",
        user_a_id="usr_host",
        user_b_id="usr_partner",
        user_a_tg_id=12345,
        user_b_tg_id=67890,
    )

    # 1. Host selects duel game -> challenge is sent to partner
    cb_select = MagicMock(spec=CallbackQuery)
    cb_select.data = "play:duel_select:carrom_clash"
    cb_select.from_user = User(id=12345, is_bot=False, first_name="Host")
    cb_select.answer = AsyncMock()
    msg_host = MagicMock(spec=Message)
    msg_host.edit_text = AsyncMock()
    cb_select.message = msg_host

    relay_mock = MagicMock()
    relay_mock.get_or_warm_session = AsyncMock(return_value=cached)

    invitation = GameInvitation(
        id="inv_9999",
        sender_id="usr_host",
        recipient_id="usr_partner",
        game_id=GameType.CARROM_CLASH,
        status=GameInvitationStatus.PENDING,
        expires_at=now + timedelta(minutes=10),
        created_at=now,
    )

    play_mock = MagicMock()
    play_mock.create_duel_invitation = AsyncMock(return_value=(True, "Challenge sent", invitation))

    ent_mock = MagicMock()
    ent_mock.can_start_duel = AsyncMock(return_value=(True, "OK", 5))

    bot_mock = MagicMock(spec=Bot)
    bot_mock.send_message = AsyncMock()

    user_repo_mock = MagicMock()

    await duel_game_select_callback(
        cb_select,
        user_repo=user_repo_mock,
        play_game_service=play_mock,
        chat_relay=relay_mock,
        gaming_entitlement_service=ent_mock,
        bot=bot_mock,
    )

    # Verify challenge sent to partner
    bot_mock.send_message.assert_called_once()
    partner_msg_call = bot_mock.send_message.call_args
    assert partner_msg_call[1]["chat_id"] == 67890
    assert "Carrom Clash" in partner_msg_call[1]["text"]
    assert "Accept Challenge & Play" in partner_msg_call[1]["reply_markup"].inline_keyboard[0][0].text

    # Verify host message updated to waiting
    msg_host.edit_text.assert_called_once()
    assert "Waiting for your partner to accept" in msg_host.edit_text.call_args[0][0]

    # 2. Partner accepts challenge -> -1 duel credit deducted from both, launch buttons sent to both
    play_session = PlayGameSession(
        id="play_ses_777",
        game_id=GameType.CARROM_CLASH,
        mode=GameMode.DUEL,
        status=PlaySessionStatus.ACTIVE,
        state_data={},
        current_turn_user_id="usr_host",
        started_at=now,
        created_at=now,
    )
    play_mock.accept_invitation = AsyncMock(return_value=(True, "Invitation accepted", play_session))
    ent_mock.get_user_entitlements = AsyncMock(return_value={"daily_duels_remaining": 4, "tier": "BASE"})

    cb_accept = MagicMock(spec=CallbackQuery)
    cb_accept.data = "duel:accept:inv_9999:carrom_clash"
    cb_accept.from_user = User(id=67890, is_bot=False, first_name="Partner")
    cb_accept.answer = AsyncMock()
    msg_partner = MagicMock(spec=Message)
    msg_partner.edit_text = AsyncMock()
    cb_accept.message = msg_partner

    bot_mock.send_message.reset_mock()

    await duel_accept_callback(
        cb_accept,
        user_repo=user_repo_mock,
        play_game_service=play_mock,
        chat_relay=relay_mock,
        gaming_entitlement_service=ent_mock,
        bot=bot_mock,
    )

    # Verify accept_invitation called with partner user id (triggers -1 quota deduction)
    play_mock.accept_invitation.assert_called_once_with(
        invitation_id="inv_9999",
        recipient_id="usr_partner",
    )

    # Verify partner received launch button
    msg_partner.edit_text.assert_called_once()
    partner_text = msg_partner.edit_text.call_args[0][0]
    assert "-1 play deducted" in partner_text
    partner_markup = msg_partner.edit_text.call_args[1]["reply_markup"]
    assert "Enter Carrom Clash" in partner_markup.inline_keyboard[0][0].text

    # Verify host received launch button via bot.send_message
    bot_mock.send_message.assert_called_once()
    host_msg_call = bot_mock.send_message.call_args
    assert host_msg_call[1]["chat_id"] == 12345
    assert "-1 play deducted" in host_msg_call[1]["text"]
    assert "Enter Carrom Clash" in host_msg_call[1]["reply_markup"].inline_keyboard[0][0].text




