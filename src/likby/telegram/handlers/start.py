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
    subscription_service: Optional[Any] = None,
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
        if profile:
            await state.clear()
            tier_name = "BASE"
            if subscription_service:
                try:
                    limits = await subscription_service.get_plan_limits(user.id)
                    tier_name = limits.get("display_name", limits.get("tier", "BASE")).upper()
                except Exception:
                    tier_name = "BASE"

            unique_tag = f"@{user.unique_id or profile.unique_id}" if (user.unique_id or profile.unique_id) else "<i>Not set</i>"
            interests_str = ", ".join(profile.interests).title() if profile.interests else "None selected"
            gender_str = profile.gender.value.replace("_", " ").title()
            karma = user.karma_score
            karma_badge = (
                "Elite Match Priority 🌟"
                if karma >= 250
                else ("Trusted Member ✨" if karma >= 100 else "Good Standing")
            )

            await message.answer(
                f"👋 <b>Welcome back to LikBy, {profile.display_name}!</b> ✨\n\n"
                f"🔒 <b>Your Profile is Safely Preserved in Memory:</b>\n"
                f"• 👤 <b>Display Name:</b> {profile.display_name}\n"
                f"• 🆔 <b>Permanent ID:</b> {unique_tag} 🔒 <i>(Immutable)</i>\n"
                f"• 🎂 <b>Age & Gender:</b> {profile.age} • {gender_str}\n"
                f"• 🎯 <b>Interests ({len(profile.interests)}):</b> {interests_str}\n"
                f"• 🌟 <b>Karma Standing:</b> {karma} / 500 ({karma_badge})\n"
                f"• 👑 <b>Membership Tier:</b> {tier_name}\n\n"
                f"🛡 <b>Privacy & Security Shield:</b>\n"
                f"• 🚫 Real Telegram @username & phone number are 100% hidden\n"
                f"• 🔐 Ephemeral zero-log messaging & content-protected media\n"
                f"• 🎮 LikBy Play Mini App is ready for live duels & solo puzzles\n\n"
                f"Ready for a connection? Tap <b>🎲 Find Match</b> below to start chatting!",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        # User is age-verified, but profile setup was incomplete (e.g. chat cleared midway)
        if user.unique_id:
            await state.update_data(unique_id=user.unique_id)
            await state.set_state(OnboardingStates.waiting_for_age)
            await message.answer(
                f"👋 <b>Welcome back to LikBy!</b>\n\n"
                f"Your permanent handle <b>@{user.unique_id}</b> is securely preserved in memory 🔒.\n\n"
                f"Let's complete your remaining profile details:\n"
                f"🎂 <b>How old are you?</b>\n"
                f"<i>(Please enter your age as a number, e.g. 24)</i>",
                parse_mode="HTML",
            )
            return
        else:
            await state.set_state(OnboardingStates.waiting_for_alias)
            await message.answer(
                "👋 <b>Welcome back to LikBy!</b>\n\n"
                "Your 18+ age verification is already confirmed ✅.\n\n"
                "🏷 <b>Choose your Display Name:</b>\n"
                "Pick a name or alias for your profile (2-30 characters).\n"
                "<i>(Names can have duplicates and can be updated anytime in your profile.)</i>",
                parse_mode="HTML",
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
        "🔒 <b>Our Core Privacy Promise:</b>\n"
        "• We <b>never</b> reveal your real Telegram username or phone number.\n"
        "• Chat messages are never permanently stored in our databases.\n"
        "• All media is content-protected against casual forwarding or saving.\n"
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
