"""
tikible.telegram.handlers.menu
Handlers for Main Menu options: Profile, Guidelines, and Help.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from tikible.repositories.interfaces import ProfileRepository, UserRepository
from tikible.telegram.keyboards import get_main_menu_keyboard
from tikible.telegram.states import EditProfileStates

router = Router(name="menu")


@router.message(F.text == "👤 My Profile")
@router.message(Command("profile"))
async def show_profile(
    message: Message,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    if not message.from_user:
        return

    tg_id = message.from_user.id
    user = await user_repo.get_by_telegram_id(tg_id)
    if not user:
        await message.answer("Please type /start to create your profile.")
        return

    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        await message.answer("Please type /start to complete your profile.")
        return

    interests_str = ", ".join(profile.interests).title() if profile.interests else "None"
    unique_tag = f"@{user.unique_id or profile.unique_id}" if (user.unique_id or profile.unique_id) else "<i>Not set</i>"

    edit_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Edit Display Name", callback_data="profile:edit_name")],
        ]
    )

    await message.answer(
        f"👤 <b>Your LikBy Profile</b>\n\n"
        f"• <b>Name:</b> {profile.display_name} <i>(non-unique)</i>\n"
        f"• <b>Unique ID:</b> {unique_tag} 🔒 <i>(Permanent — cannot be edited)</i>\n"
        f"• <b>Age:</b> {profile.age}\n"
        f"• <b>Gender:</b> {profile.gender.value.replace('_', ' ').title()}\n"
        f"• <b>Interests:</b> {interests_str}\n"
        f"• <b>Karma Score:</b> {user.karma_score} / 100 🌟\n\n"
        f"<i>Your Telegram username and phone number are never shared.</i>",
        parse_mode="HTML",
        reply_markup=edit_kb,
    )


@router.callback_query(F.data == "profile:edit_name")
async def start_edit_name(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return

    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    await state.set_state(EditProfileStates.waiting_for_new_name)
    unique_tag = f"@{user.unique_id or profile.unique_id}" if (user.unique_id or profile.unique_id) else "Not set"
    await callback.message.answer(
        f"✏️ <b>Change Display Name</b>\n\n"
        f"Current Name: <b>{profile.display_name}</b>\n"
        f"Unique ID: <b>{unique_tag}</b> 🔒 <i>(Permanent — cannot be edited)</i>\n\n"
        f"Please send your new display name (2-30 characters):\n"
        f"<i>(Multiple users may share the same display name.)</i>",
        parse_mode="HTML",
    )


@router.message(EditProfileStates.waiting_for_new_name)
async def process_new_name(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    new_name = (message.text or "").strip()
    if len(new_name) < 2 or len(new_name) > 30:
        await message.answer(
            "⚠️ Display name must be between 2 and 30 characters. Please try again:"
        )
        return

    if not message.from_user:
        return

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        return

    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    profile.update_display_name(new_name)
    await profile_repo.save(profile)
    await state.clear()

    unique_tag = f"@{user.unique_id or profile.unique_id}" if (user.unique_id or profile.unique_id) else "Not set"
    await message.answer(
        f"✅ <b>Display Name Updated!</b>\n\n"
        f"• <b>New Name:</b> {profile.display_name} <i>(non-unique)</i>\n"
        f"• <b>Unique ID:</b> {unique_tag} 🔒 <i>(Permanent — cannot be edited)</i>",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )


@router.message(F.text == "📜 Guidelines")
@router.message(Command("guidelines"))
async def show_guidelines(message: Message) -> None:
    await message.answer(
        "📜 <b>Community Guidelines</b>\n\n"
        "1. <b>Respect Anonymity:</b> Do not ask for or share personal contact information (usernames, phone numbers, addresses).\n"
        "2. <b>Zero Tolerance for Harassment:</b> Hate speech, threats, and bullying will lead to immediate bans.\n"
        "3. <b>Adults Only (18+):</b> Tikible is strictly for adult users.\n"
        "4. <b>Safe Content:</b> Non-consensual explicit content and commercial spam are strictly prohibited.\n\n"
        "<i>Use the ⚠️ Report button at any time to immediately exit and block an abusive partner.</i>",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )


@router.message(F.text == "❓ Help / About")
@router.message(Command("help"))
async def show_help(message: Message) -> None:
    await message.answer(
        "❓ <b>About LikBy</b>\n\n"
        "LikBy is a privacy-first anonymous social matching platform.\n\n"
        "<b>How it works:</b>\n"
        "1. Tap <b>🎲 Find a Match</b> to enter the matching queue.\n"
        "2. We pair you with someone who shares your interests.\n"
        "3. Chat anonymously in real time! We never store your message text.\n"
        "4. Challenge your partner to <b>🎮 Play Game</b> (Tic-Tac-Toe) anytime.\n"
        "5. Tap <b>⏭ Next Chat</b> to skip or <b>🚫 End Chat</b> to leave.\n\n"
        "Have fun and make meaningful connections! ✨",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )
