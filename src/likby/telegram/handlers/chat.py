"""
likby.telegram.handlers.chat
Handlers for anonymous real-time message relaying, media forwarding, /stop, /next, and transcript export.
"""

from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from likby.domain.enums import MessageType, RatingType, TerminationReason, UserState
from likby.repositories.interfaces import (
    ChatSessionRepository,
    ProfileRepository,
    UserRepository,
)
from likby.config import get_settings
from likby.services.chat_relay_service import ChatRelayService
from likby.services.karma_service import KarmaService
from likby.services.matchmaking_service import MatchmakingService
from likby.services.media_quota_service import MediaQuotaService
from likby.services.social_service import SocialService
from likby.services.transcript_service import TranscriptService
from likby.telegram.handlers.play import (
    DUEL_GAMES_DETAILS,
    DUEL_NUM_MAP,
    SOLO_GAMES_DETAILS,
    SOLO_NUM_MAP,
    format_duel_card,
    format_solo_card,
)
from likby.telegram.keyboards import (
    get_active_chat_keyboard,
    get_chat_hub_keyboard,
    get_duel_game_card_keyboard,
    get_duel_games_keyboard,
    get_main_menu_keyboard,
    get_post_session_keyboard,
    get_solo_game_card_keyboard,
    get_solo_games_keyboard,
)

router = Router(name="chat")


@router.message(F.text == "🚫 End Chat")
@router.message(Command("stop"))
@router.callback_query(F.data == "chat:end")
async def handle_stop_chat(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    chat_relay: ChatRelayService,
) -> None:
    message = event if isinstance(event, Message) else event.message
    if isinstance(event, CallbackQuery):
        await event.answer()

    if not event.from_user:
        return

    tg_id = event.from_user.id
    user = await user_repo.get_by_telegram_id(tg_id)
    if user:
        user.transition_state(UserState.MAIN_MENU)
        await user_repo.save(user)

    cached = await chat_relay.get_or_warm_session(tg_id)
    session_id = cached.session_id if cached else None
    partner_id = (
        (cached.user_b_id if cached.user_a_tg_id == tg_id else cached.user_a_id)
        if cached
        else None
    )

    ended = await chat_relay.end_active_session(
        sender_tg_id=tg_id,
        reason=TerminationReason.USER_STOPPED,
    )

    if ended and session_id and partner_id:
        await message.answer(
            "🛑 <b>Chat ended.</b>\nHow was your conversation? You can rate your partner, express interest in friendship, or save the transcript.",
            parse_mode="HTML",
            reply_markup=get_post_session_keyboard(session_id, partner_id),
        )
    else:
        await message.answer(
            "You are not currently in an active chat.",
            reply_markup=get_main_menu_keyboard(),
        )


@router.message(F.text == "⏭ Next Chat")
@router.message(Command("next"))
@router.callback_query(F.data == "chat:next")
async def handle_next_chat(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
    chat_relay: ChatRelayService,
    match_service: MatchmakingService,
) -> None:
    message = event if isinstance(event, Message) else event.message
    if isinstance(event, CallbackQuery):
        await event.answer()

    if not event.from_user:
        return

    tg_id = event.from_user.id
    user = await user_repo.get_by_telegram_id(tg_id)
    if not user:
        return

    # 1. End current session if active
    await chat_relay.end_active_session(
        sender_tg_id=tg_id,
        reason=TerminationReason.USER_SKIPPED,
    )

    # 2. Re-enqueue immediately
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        await message.answer("Please type /start to set up your profile.", reply_markup=get_main_menu_keyboard())
        return

    await match_service.enqueue(user_id=user.id, profile=profile)
    user.transition_state(UserState.IN_QUEUE)
    await user_repo.save(user)

    # Check for instant match
    matches = await match_service.run_matchmaker_cycle()
    for tkt_a, tkt_b, session in matches:
        if tkt_a.user_id == user.id or tkt_b.user_id == user.id:
            user.transition_state(UserState.IN_CHAT)
            await user_repo.save(user)
            await chat_relay.record_system_event(session.id, "Session started.")
            await message.answer(
                "🎉 <b>Connected to a new conversation partner!</b>",
                parse_mode="HTML",
                reply_markup=get_active_chat_keyboard(),
            )
            return

    await message.answer(
        "⏭ <b>Skipped. Looking for someone new...</b>",
        parse_mode="HTML",
    )


# --- Media Message Handlers & Quota Inspections ---

@router.message(Command("my_media_usage"))
@router.message(F.text == "📊 My Media Usage")
async def handle_my_media_usage(
    message: Message,
    user_repo: UserRepository,
    media_quota_service: MediaQuotaService,
) -> None:
    if not message.from_user:
        return
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Please type /start to set up your profile.")
        return

    summary = await media_quota_service.get_user_media_usage_summary(user.id)
    text = (
        f"💜 <b>LikBy Media Usage & Protection</b>\n\n"
        f"<b>Current Plan:</b> {summary['plan_name']}\n"
        f"<b>Daily Uploads:</b> {summary['uploads_used']} / {summary['uploads_limit']} used ({summary['uploads_remaining']} remaining)\n"
        f"<b>Daily Received:</b> {summary['received_used']} / {summary['received_limit']} used ({summary['received_remaining']} remaining)\n\n"
        f"<b>Max Image Size:</b> {summary['max_image_mb']} MB\n"
        f"<b>Max Video Size:</b> {summary['max_video_mb']} MB\n"
        f"<b>Next Daily Reset:</b> 00:00 UTC\n\n"
        f"🛡 <b>Content Protection Active:</b>\n"
        f"All shared photos, videos, and media have saving and forwarding restricted via Telegram Content Protection.\n"
        f"<i>Note: Content protection is a platform mitigation; physical hardware capture cannot be universally prevented.</i>\n\n"
        f"Upgrade your daily allowance anytime with /subscribe."
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.photo)
async def handle_chat_photo(message: Message, chat_relay: ChatRelayService) -> None:
    if not message.from_user or not message.photo:
        return
    cached = await chat_relay.get_or_warm_session(message.from_user.id)
    if not cached:
        await message.answer("You are not currently in an active chat.")
        return
    highest_res = message.photo[-1]
    await chat_relay.relay_media(
        sender_tg_id=message.from_user.id,
        message_type=MessageType.PHOTO,
        file_id=highest_res.file_id,
        caption=message.caption,
        file_size=highest_res.file_size,
    )


@router.message(F.video)
async def handle_chat_video(message: Message, chat_relay: ChatRelayService) -> None:
    if not message.from_user or not message.video:
        return
    cached = await chat_relay.get_or_warm_session(message.from_user.id)
    if not cached:
        await message.answer("You are not currently in an active chat.")
        return
    await chat_relay.relay_media(
        sender_tg_id=message.from_user.id,
        message_type=MessageType.VIDEO,
        file_id=message.video.file_id,
        caption=message.caption,
        file_name=message.video.file_name,
        mime_type=message.video.mime_type,
        file_size=message.video.file_size,
    )


@router.message(F.voice)
async def handle_chat_voice(message: Message, chat_relay: ChatRelayService) -> None:
    if not message.from_user or not message.voice:
        return
    cached = await chat_relay.get_or_warm_session(message.from_user.id)
    if not cached:
        await message.answer("You are not currently in an active chat.")
        return
    await chat_relay.relay_media(
        sender_tg_id=message.from_user.id,
        message_type=MessageType.VOICE,
        file_id=message.voice.file_id,
        caption=message.caption,
        mime_type=message.voice.mime_type,
        file_size=message.voice.file_size,
    )


@router.message(F.document)
async def handle_chat_document(message: Message, chat_relay: ChatRelayService) -> None:
    if not message.from_user or not message.document:
        return
    cached = await chat_relay.get_or_warm_session(message.from_user.id)
    if not cached:
        await message.answer("You are not currently in an active chat.")
        return
    await chat_relay.relay_media(
        sender_tg_id=message.from_user.id,
        message_type=MessageType.DOCUMENT,
        file_id=message.document.file_id,
        caption=message.caption,
        file_name=message.document.file_name,
        mime_type=message.document.mime_type,
        file_size=message.document.file_size,
    )


@router.message(F.sticker)
async def handle_chat_sticker(message: Message, chat_relay: ChatRelayService) -> None:
    if not message.from_user or not message.sticker:
        return
    cached = await chat_relay.get_or_warm_session(message.from_user.id)
    if not cached:
        await message.answer("You are not currently in an active chat.")
        return
    await chat_relay.relay_media(
        sender_tg_id=message.from_user.id,
        message_type=MessageType.STICKER,
        file_id=message.sticker.file_id,
    )


# --- Text Message Handler ---

@router.message(F.text)
async def handle_chat_message(
    message: Message,
    user_repo: UserRepository,
    chat_relay: ChatRelayService,
) -> None:
    """Relays text messages with durable persistence between active partners."""
    if not message.from_user or not message.text:
        return

    tg_id = message.from_user.id
    text = message.text

    # Ignore system menu commands that might fall through
    menu_buttons = [
        "🎲 Find Match", "🎲 Find a Match", "🎲 Find Someone", "💬 My Chats", "👥 Connections",
        "👤 Profile & VIP", "🎮 LikBy Play", "💙 Who Liked Me",
        "👥 My Friends", "🔍 Search ID", "📬 Requests", "👤 My Profile",
        "🌟 My Karma", "💎 Subscription", "🕹 Solo Arcade", "🛡 Help & Safety",
        "📜 Guidelines", "❓ Help / About",
    ]
    if text in menu_buttons:
        return

    relayed = await chat_relay.relay_text(sender_tg_id=tg_id, text=text)
    if not relayed:
        clean_text = text.strip().lower()
        if clean_text in SOLO_NUM_MAP:
            game_id = SOLO_NUM_MAP[clean_text]
            info = SOLO_GAMES_DETAILS.get(game_id)
            if info:
                settings = get_settings()
                mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"
                card_text = format_solo_card(info, mini_app_url)
                kb = get_solo_game_card_keyboard(game_id, mini_app_url)
                await message.answer(card_text, parse_mode="HTML", reply_markup=kb)
                return

        if clean_text in DUEL_NUM_MAP:
            game_id = DUEL_NUM_MAP[clean_text]
            info = DUEL_GAMES_DETAILS.get(game_id)
            if info:
                settings = get_settings()
                mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"
                card_text = format_duel_card(info, mini_app_url)
                kb = get_duel_game_card_keyboard(game_id, mini_app_url, in_active_session=False)
                await message.answer(card_text, parse_mode="HTML", reply_markup=kb)
                return

        if clean_text in ["duels", "duel", "multiplayer", "2 player", "2-player"]:
            settings = get_settings()
            mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"
            duel_text = (
                "⚔️ <b>LikBy Play — Multiplayer Duels</b>\n\n"
                "<i>Duels unlock live with your chat partner or practice vs AI!</i>\n\n"
                "1. 🔴 <b>Connect Four</b> — <i>Align 4 discs in 7x6 grid</i>\n"
                "2. 🎯 <b>Carrom Clash</b> — <i>Striker physics & Queen rules</i>\n"
                "3. 🏒 <b>Air Rush</b> — <i>Fast-paced kinetic air hockey</i>\n"
                "4. 🎱 <b>Pocket Pool</b> — <i>8-Ball billiards & cue physics</i>\n"
                "5. 🤺 <b>Stick Arena</b> — <i>Martial combat platform brawler</i>\n"
                "6. 🎨 <b>QuickDraw</b> — <i>Real-time sketch & guess race</i>\n"
                "7. 🔤 <b>Word Rush</b> — <i>Shared letter pool vocabulary race</i>\n"
                "8. 🧠 <b>Brain Blitz</b> — <i>Simultaneous esports trivia battle</i>\n"
                "9. ⚡️ <b>Reflex Rush</b> — <i>Sub-180ms reaction test chamber</i>\n"
                "10. 💭 <b>MindMatch</b> — <i>Social compatibility & harmony</i>\n"
                "11. 🔍 <b>Mystery Mission</b> — <i>Co-op escape room clues</i>\n\n"
                "👉 <b>Tap any game button below to select and view rules or challenge!</b>"
            )
            await message.answer(duel_text, parse_mode="HTML", reply_markup=get_duel_games_keyboard(mini_app_url))
            return

        if clean_text in ["solo", "play", "games", "game", "arcade", "solo games"]:
            settings = get_settings()
            mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"
            solo_text = (
                "🧩 <b>LikBy Play — Solo Experiences</b>\n\n"
                "✨ <b>100% Free & Unlimited for all tiers!</b>\n"
                "<i>Solo games never consume duel quota and do NOT require an active chat session.</i>\n\n"
                "1. 🧘 <b>Zen Merge (2048)</b> — <i>Sliding tile puzzle (Goal: 2048)</i>\n"
                "2. 🔤 <b>Word Hunt</b> — <i>5x5 matrix vocabulary search</i>\n"
                "3. 🎨 <b>Color Flow</b> — <i>Connect matching neon paths</i>\n"
                "4. ⛳️ <b>Pocket Golf</b> — <i>Precision slingshot mini-golf</i>\n"
                "5. ⚡️ <b>Reflex Lab</b> — <i>Sub-200ms neuro speed test</i>\n"
                "6. 🔍 <b>Daily Mystery</b> — <i>Cryptic lateral riddles & secrets</i>\n\n"
                "👉 <b>Tap any game button below or type its number (1-6) to play instantly!</b>"
            )
            await message.answer(solo_text, parse_mode="HTML", reply_markup=get_solo_games_keyboard(mini_app_url))
            return

        settings = get_settings()
        mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"
        idle_prompt = (
            "💬 <b>You are not currently in an active chat session.</b>\n\n"
            "• Tap <b>🎲 Find Match</b> below to connect with a conversation partner.\n"
            "• Or play <b>Free Solo Games</b> anytime with zero wait:\n"
            "  Type <b>1 to 6</b> (e.g. <code>1</code> for Zen Merge, <code>4</code> for Pocket Golf) or tap <b>🧩 Solo Games</b> below!"
        )
        await message.answer(
            idle_prompt,
            parse_mode="HTML",
            reply_markup=get_chat_hub_keyboard(is_active=False, mini_app_url=mini_app_url),
        )


# --- Post-Session & Transcript Callbacks ---

@router.callback_query(F.data.startswith("rate:"))
async def handle_rating_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    karma_service: KarmaService,
) -> None:
    """Handle post-session like/dislike rating."""
    if not callback.data or not callback.from_user:
        return

    parts = callback.data.split(":")
    if len(parts) < 3:
        return

    session_id, action = parts[1], parts[2]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("User profile not found.", show_alert=True)
        return

    rating_type = RatingType.LIKE if action == "like" else RatingType.DISLIKE
    success, msg, _ = await karma_service.rate_session(
        session_id=session_id,
        rater_id=user.id,
        rating_type=rating_type,
    )
    await callback.answer(msg, show_alert=True)


@router.callback_query(F.data.startswith("social_like:"))
async def handle_social_like_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    social_service: SocialService,
) -> None:
    """Handle post-session mutual like (friendship interest)."""
    if not callback.data or not callback.from_user:
        return

    parts = callback.data.split(":")
    if len(parts) < 3:
        return

    session_id, partner_id = parts[1], parts[2]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("User profile not found.", show_alert=True)
        return

    success, msg, _ = await social_service.express_like(
        sender_id=user.id,
        target_id=partner_id,
        session_id=session_id,
    )
    await callback.answer(msg, show_alert=True)


@router.callback_query(F.data.startswith("transcript:export:"))
async def handle_transcript_export_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    session_repo: ChatSessionRepository,
    transcript_service: TranscriptService,
    bot: Bot,
) -> None:
    """Export human-readable chat transcript as a .txt document."""
    if not callback.data or not callback.from_user:
        return

    session_id = callback.data.split(":")[2]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("User not found.")
        return

    # Verify authorization (requester must be participant)
    session = await session_repo.get_by_id(session_id)
    if not session or (user.id != session.user_a_id and user.id != session.user_b_id):
        await callback.answer("Unauthorized: You were not a participant in this session.", show_alert=True)
        return

    export = await transcript_service.export_transcript_bytes(session_id)
    if not export:
        await callback.answer("No transcript available for this session.", show_alert=True)
        return

    filename, file_bytes = export
    doc = BufferedInputFile(file_bytes, filename=filename)

    await bot.send_document(
        chat_id=callback.from_user.id,
        document=doc,
        caption="📜 <b>LikBy Chat Session Transcript</b>\nSaved in human-readable plain text format.",
        parse_mode="HTML",
    )
    await callback.answer("Transcript sent!")
