"""
likby.telegram.handlers.start
Handlers for /start command and 18+ age verification gate.
"""

from typing import Any, Optional
import uuid
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from likby.domain.entities.user import User
from likby.domain.enums import UserState
from likby.repositories.interfaces import ProfileRepository, UserRepository
from likby.telegram.keyboards import get_age_gate_keyboard, get_main_menu_keyboard
from likby.telegram.states import OnboardingStates
from likby.telegram.utils import safe_edit_text

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
    referral_service: Optional[Any] = None,
) -> None:
    if not message.from_user:
        return

    tg_id = message.from_user.id
    user = await user_repo.get_by_telegram_id(tg_id)

    # Check for referral code in deep link (e.g. /start ref_alice)
    ref_code = None
    if message.text and "ref_" in message.text:
        try:
            ref_code = message.text.split("ref_")[1].strip().split()[0]
        except Exception:
            ref_code = None

    if user and user.age_verified and user.state != UserState.ONBOARDING_AGE_GATE:
        profile = await profile_repo.get_by_user_id(user.id)
        name = profile.display_name if profile else "Friend"
        await state.clear()
        await message.answer(
            f"👋 <b>Welcome back, {name}!</b>\n\n"
            "Ready for a conversation? Tap <b>🎲 Find a Match</b> below.",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    # New or unverified user
    if not user:
        user = User(
            id=f"usr_{uuid.uuid4().hex[:12]}",
            telegram_id=tg_id,
        )
        await user_repo.save(user)

    # Register referral intent if incoming from referral link
    if ref_code and referral_service:
        try:
            await referral_service.register_referral_intent(ref_code, user.id)
        except Exception:
            pass

    await state.set_state(OnboardingStates.waiting_for_age_gate)
    await message.answer(
        "👋 <b>Welcome to LikBy.</b>\n\n"
        "LikBy connects you with compatible people for <b>100% anonymous, real-time conversations</b>.\n\n"
        "🔒 <b>Our core promise:</b>\n"
        "• We never reveal your Telegram username or phone number.\n"
        "• Chat messages are never stored permanently in our database.\n"
        "• You can exit, skip, or block at any moment.\n\n"
        "⚠️ <i>To ensure a safe environment, you must be 18 years or older.</i>",
        parse_mode="HTML",
        reply_markup=get_age_gate_keyboard(),
    )


@router.callback_query(F.data == "age_verify:accept")
async def handle_age_accept(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if user:
        user.verify_age()
        await user_repo.save(user)

    await state.set_state(OnboardingStates.waiting_for_alias)
    await safe_edit_text(
        callback.message,
        "✅ <b>Age verified (18+).</b>\n\n"
        "🏷 <b>Choose your Display Name</b>\n"
        "Pick a name or alias for your profile (2-30 characters).\n"
        "<i>(Names can allow duplicates and can be updated anytime.)</i>",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "age_verify:reject")
async def handle_age_reject(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if callback.message:
        await safe_edit_text(
            callback.message,
            "🛑 <b>Access Restricted</b>\n\n"
            "LikBy is strictly for adults aged 18 and older.\n"
            "Thank you for your honesty. We look forward to welcoming you when you are 18!",
            parse_mode="HTML",
        )
