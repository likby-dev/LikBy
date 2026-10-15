"""
tikible.telegram.handlers.chat
Handlers for anonymous real-time message relaying, /stop, and /next.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from tikible.domain.enums import TerminationReason, UserState
from tikible.repositories.interfaces import ProfileRepository, UserRepository
from tikible.services.chat_relay_service import ChatRelayService
from tikible.services.matchmaking_service import MatchmakingService
from tikible.telegram.keyboards import get_active_chat_keyboard, get_main_menu_keyboard

router = Router(name="chat")


@router.message(F.text == "🚫 End Chat")
@router.message(Command("stop"))
async def handle_stop_chat(
    message: Message,
    user_repo: UserRepository,
    chat_relay: ChatRelayService,
) -> None:
    if not message.from_user:
        return

    tg_id = message.from_user.id
    user = await user_repo.get_by_telegram_id(tg_id)
    if user:
        user.transition_state(UserState.MAIN_MENU)
        await user_repo.save(user)

    ended = await chat_relay.end_active_session(
        sender_tg_id=tg_id,
        reason=TerminationReason.USER_STOPPED,
    )
    if ended:
        await message.answer(
            "🛑 <b>Chat ended.</b>\nReturned to Main Menu.",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
    else:
        await message.answer(
            "You are not currently in an active chat.",
            reply_markup=get_main_menu_keyboard(),
        )


@router.message(F.text == "⏭ Next Chat")
@router.message(Command("next"))
async def handle_next_chat(
    message: Message,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
    chat_relay: ChatRelayService,
    match_service: MatchmakingService,
) -> None:
    if not message.from_user:
        return

    tg_id = message.from_user.id
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


@router.message(F.text)
async def handle_chat_message(
    message: Message,
    user_repo: UserRepository,
    chat_relay: ChatRelayService,
) -> None:
    """Relays text messages strictly in-memory between active partners."""
    if not message.from_user or not message.text:
        return

    tg_id = message.from_user.id
    text = message.text

    # Ignore system menu commands that might fall through
    if text in ["🎲 Find a Match", "🕹 Solo Arcade", "👤 My Profile", "⚙️ Preferences", "📜 Guidelines", "❓ Help / About"]:
        return

    relayed = await chat_relay.relay_text(sender_tg_id=tg_id, text=text)
    if not relayed:
        await message.answer(
            "You are not currently in an active chat.\nTap <b>🎲 Find a Match</b> to connect!",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
