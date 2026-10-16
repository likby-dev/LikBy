"""
likby.telegram.handlers.matchmaking
Handlers for queue enrollment, match searching, and cancellation.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from likby.domain.enums import UserState
from likby.repositories.interfaces import ProfileRepository, UserRepository
from likby.services.matchmaking_service import MatchmakingService
from likby.telegram.keyboards import (
    get_active_chat_keyboard,
    get_main_menu_keyboard,
    get_queue_cancel_keyboard,
)

router = Router(name="matchmaking")


from likby.services.chat_relay_service import ChatRelayService


@router.message(F.text.in_(["🎲 Find Someone", "🎲 Find a Match"]))
@router.message(Command("find"))
@router.callback_query(F.data == "queue:find_new")
async def start_search(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
    match_service: MatchmakingService,
    chat_relay: ChatRelayService,
) -> None:
    message = event if isinstance(event, Message) else event.message
    if isinstance(event, CallbackQuery):
        await event.answer()

    if not message.from_user:
        return

    tg_id = message.from_user.id
    user = await user_repo.get_by_telegram_id(tg_id)
    if not user:
        await message.answer("Please type /start to set up your profile first.")
        return

    if not user.age_verified:
        await message.answer("Please complete age verification first by typing /start.")
        return

    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        await message.answer("Please complete your profile first by typing /start.")
        return

    # Enqueue ticket
    ticket = await match_service.enqueue(user_id=user.id, profile=profile)
    user.transition_state(UserState.IN_QUEUE)
    await user_repo.save(user)

    # Immediately attempt matchmaking cycle
    matches = await match_service.run_matchmaker_cycle()

    # Check if this user was matched immediately
    for tkt_a, tkt_b, session in matches:
        if tkt_a.user_id == user.id or tkt_b.user_id == user.id:
            # Matched! Notify both users
            partner_id = session.get_partner_id(user.id)
            partner_profile = await profile_repo.get_by_user_id(partner_id)
            common_ints = session.match_metadata.get("common_interests", [])
            ints_str = ", ".join(common_ints).title() if common_ints else "Mutual Curiosity"

            # Set users state to IN_CHAT
            user.transition_state(UserState.IN_CHAT)
            await user_repo.save(user)
            partner_user = await user_repo.get_by_id(partner_id)
            if partner_user:
                partner_user.transition_state(UserState.IN_CHAT)
                await user_repo.save(partner_user)

            await chat_relay.record_system_event(session.id, "Session started.")

            await message.bot.send_message(
                chat_id=tg_id,
                text=(
                    "🎉 <b>Connected to an anonymous partner!</b>\n\n"
                    f"🤝 <b>Common ground:</b> {ints_str}\n"
                    "💬 <i>Messages you send here are forwarded anonymously.</i>\n\n"
                    "Commands:\n"
                    "• <code>🎮 Play Game</code> — Challenge partner to Tic-Tac-Toe\n"
                    "• <code>⏭ Next Chat</code> — Connect with someone new\n"
                    "• <code>🚫 End Chat</code> — Finish conversation"
                ),
                parse_mode="HTML",
                reply_markup=get_active_chat_keyboard(),
            )
            if partner_user:
                await message.bot.send_message(
                    chat_id=partner_user.telegram_id,
                    text=(
                        "🎉 <b>Connected to an anonymous partner!</b>\n\n"
                        f"🤝 <b>Common ground:</b> {ints_str}\n"
                        "💬 <i>Messages you send here are forwarded anonymously.</i>\n\n"
                        "Commands:\n"
                        "• <code>🎮 Play Game</code> — Challenge partner to Tic-Tac-Toe\n"
                        "• <code>⏭ Next Chat</code> — Connect with someone new\n"
                        "• <code>🚫 End Chat</code> — Finish conversation"
                    ),
                    parse_mode="HTML",
                    reply_markup=get_active_chat_keyboard(),
                )
            return

    # If not matched immediately, display waiting queue UI
    await message.answer(
        "🔍 <b>Looking for a conversation partner...</b>\n\n"
        "<i>Matching you based on your age preferences and mutual interests.</i>\n"
        "⏱ <i>Estimated wait: ~15 to 45 seconds</i>",
        parse_mode="HTML",
        reply_markup=get_queue_cancel_keyboard(),
    )


@router.callback_query(F.data == "queue:cancel")
async def cancel_search(
    callback: CallbackQuery,
    user_repo: UserRepository,
    match_service: MatchmakingService,
) -> None:
    await callback.answer("Search cancelled.")
    if not callback.from_user or not callback.message:
        return

    tg_id = callback.from_user.id
    user = await user_repo.get_by_telegram_id(tg_id)
    if user:
        await match_service.cancel(user.id)
        user.transition_state(UserState.MAIN_MENU)
        await user_repo.save(user)

    await callback.message.delete()
    await callback.message.answer(
        "❌ <b>Search cancelled.</b>\nReturned to Main Menu.",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )
