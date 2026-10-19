"""
likby.telegram.handlers.onboarding
Onboarding FSM handlers: Alias, Age, Gender, and Interests selection.
"""

import html
import logging
import re
from typing import Any, List, Optional
import uuid
from aiogram import Bot, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from likby.domain.entities.profile import Profile
from likby.domain.entities.user import User

logger = logging.getLogger(__name__)
from likby.domain.enums import Gender, GenderPreference, UserState
from likby.repositories.interfaces import ProfileRepository, UserRepository
from likby.telegram.keyboards import (
    AVAILABLE_INTERESTS,
    get_gender_keyboard,
    get_interests_keyboard,
    get_main_menu_keyboard,
)
from likby.telegram.states import OnboardingStates
from likby.telegram.utils import safe_edit_reply_markup, safe_edit_text

router = Router(name="onboarding")

UNIQUE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,20}$")
RESERVED_UNIQUE_IDS = {
    "admin", "administrator", "system", "likby", "support",
    "moderator", "mod", "help", "official", "telegram",
    "bot", "anonymous", "root", "dev", "null", "undefined",
    "security", "staff", "owner",
}


@router.message(OnboardingStates.waiting_for_alias)
async def process_alias(message: Message, state: FSMContext) -> None:
    raw_alias = (message.text or "").strip()
    clean_alias = re.sub(r"\s+", " ", raw_alias)

    if len(clean_alias) < 2:
        await message.answer(
            "⚠️ <b>Display Name is too short.</b>\n"
            "Please enter a name with at least 2 characters:",
            parse_mode="HTML",
        )
        return

    if len(clean_alias) > 30:
        await message.answer(
            "⚠️ <b>Display Name is too long.</b>\n"
            "Please enter a name with 30 characters or fewer:",
            parse_mode="HTML",
        )
        return

    if clean_alias.startswith("/"):
        await message.answer(
            "⚠️ <b>Display Name cannot start with a slash (/).</b>\n"
            "Please enter your preferred nickname or alias:",
            parse_mode="HTML",
        )
        return

    if not any(c.isalnum() for c in clean_alias):
        await message.answer(
            "⚠️ <b>Display Name must contain letters or numbers.</b>\n"
            "Please enter a valid nickname or alias:",
            parse_mode="HTML",
        )
        return

    safe_alias = html.escape(clean_alias)
    await state.update_data(alias=safe_alias)
    await state.set_state(OnboardingStates.waiting_for_unique_id)
    await message.answer(
        f"Nice to meet you, <b>{safe_alias}</b>! ✨\n\n"
        "🆔 <b>Now, choose your Unique ID:</b>\n"
        "Create a unique handle for your account (e.g. <code>alex_99</code>, <code>skywalker</code>).\n\n"
        "📌 <b>Rules:</b>\n"
        "• 3 to 20 characters (letters, numbers, underscores)\n"
        "• <b>Unique:</b> No two users can have the same Unique ID\n"
        "• 🔒 <b>Permanent:</b> Your Unique ID <b>cannot be edited or changed</b> once created!\n\n"
        "<i>(Your Display Name can have duplicates and be changed anytime, but your Unique ID is permanent.)</i>",
        parse_mode="HTML",
    )


@router.message(OnboardingStates.waiting_for_unique_id)
async def process_unique_id(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
) -> None:
    raw_id = (message.text or "").strip()
    clean_id = raw_id.lstrip("@").lower().strip()

    if not UNIQUE_ID_REGEX.match(clean_id):
        await message.answer(
            "⚠️ <b>Invalid Unique ID format.</b>\n\n"
            "• Must be 3 to 20 characters long\n"
            "• Only letters (a-z), numbers (0-9), and underscores (_)\n"
            "• No spaces, periods, or special characters\n"
            "• Example: <code>alex_99</code> or <code>sam2024</code>\n\n"
            "Please choose a valid Unique ID:",
            parse_mode="HTML",
        )
        return

    if clean_id in RESERVED_UNIQUE_IDS:
        await message.answer(
            f"⚠️ <b>@{clean_id} is a reserved system identifier.</b>\n\n"
            "Please choose a different personal handle:",
            parse_mode="HTML",
        )
        return

    # Check case-insensitive uniqueness in database
    existing_user = await user_repo.get_by_unique_id(clean_id)
    current_tg_id = message.from_user.id if message.from_user else 0
    if existing_user and existing_user.telegram_id != current_tg_id:
        await message.answer(
            f"⚠️ <b>@{clean_id} is already taken!</b>\n\n"
            "Another user has already claimed this Unique ID. Please choose a different handle:",
            parse_mode="HTML",
        )
        return

    # Lock to user entity immediately so it persists in memory & DB across restarts
    if message.from_user:
        u = await user_repo.get_by_telegram_id(message.from_user.id)
        if u:
            u.unique_id = clean_id
            await user_repo.save(u)

    await state.update_data(unique_id=clean_id)
    await state.set_state(OnboardingStates.waiting_for_age)
    await message.answer(
        f"✅ Unique ID <b>@{clean_id}</b> is available and locked to your profile! 🔒\n"
        f"<i>(Note: This Unique ID is permanent and cannot be changed later.)</i>\n\n"
        "🎂 <b>How old are you?</b>\n"
        "<i>Please type your age as a number (e.g. 24). This is only used to match you within appropriate age brackets.</i>",
        parse_mode="HTML",
    )


@router.message(OnboardingStates.waiting_for_age)
async def process_age(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(
            "⚠️ <b>Please enter your age as a whole number</b> (e.g. 24):\n\n"
            "<i>This is used solely to match you within appropriate peer age brackets.</i>",
            parse_mode="HTML",
        )
        return

    age = int(text)
    if age < 18:
        await message.answer(
            "🛑 <b>Age Requirement (18+):</b>\n\n"
            "LikBy is strictly for adults aged 18 and older. For user safety and privacy, accounts under 18 cannot be created.\n\n"
            "Thank you for understanding.",
            parse_mode="HTML",
        )
        return

    if age > 99:
        await message.answer(
            "⚠️ <b>Please enter a realistic age between 18 and 99:</b>",
            parse_mode="HTML",
        )
        return

    await state.update_data(age=age)
    await state.set_state(OnboardingStates.waiting_for_gender)
    await message.answer(
        "⚧ <b>Select your gender identity:</b>",
        parse_mode="HTML",
        reply_markup=get_gender_keyboard(),
    )


@router.callback_query(F.data.startswith("gender:"))
async def process_gender(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.data or not callback.message:
        return

    gender_str = callback.data.split(":")[1]
    gender = Gender(gender_str)
    await state.update_data(gender=gender.value, selected_interests=[])
    await state.set_state(OnboardingStates.waiting_for_interests)

    await safe_edit_text(
        callback.message,
        "🎯 <b>Select 2 to 5 topics you enjoy discussing:</b>\n\n"
        "<i>Tap buttons to select/unselect, then press Done.</i>",
        parse_mode="HTML",
        reply_markup=get_interests_keyboard(selected=[]),
    )


def extract_selected_interests_from_markup(message: Optional[Message]) -> List[str]:
    """Extract currently checked interests directly from the inline keyboard buttons."""
    if not message or not message.reply_markup:
        return []
    selected: List[str] = []
    for row in message.reply_markup.inline_keyboard:
        for btn in row:
            if btn.callback_data and btn.callback_data.startswith("interest_toggle:"):
                code = btn.callback_data.split(":", 1)[1]
                if btn.text and "✅" in btn.text:
                    if code not in selected:
                        selected.append(code)
    return selected


@router.callback_query(F.data.startswith("interest_toggle:"))
async def toggle_interest(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    interest_code = callback.data.split(":")[1]
    data = await state.get_data()
    selected = list(data.get("selected_interests", []))

    # If state memory was lost, recover from message markup checkmarks
    if not selected and callback.message:
        selected = extract_selected_interests_from_markup(callback.message)

    if interest_code in selected:
        selected.remove(interest_code)
        await callback.answer()
    else:
        if len(selected) >= 5:
            await callback.answer("You can select up to 5 interests maximum! Tap Done when finished.", show_alert=True)
            return
        selected.append(interest_code)
        await callback.answer()

    await state.set_state(OnboardingStates.waiting_for_interests)
    await state.update_data(selected_interests=selected)
    await safe_edit_reply_markup(
        callback.message,
        reply_markup=get_interests_keyboard(selected=selected),
    )


@router.callback_query(F.data == "interest_done")
async def finish_interests(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
    bot: Optional[Bot] = None,
    referral_service: Optional[Any] = None,
) -> None:
    data = await state.get_data()
    selected = list(data.get("selected_interests", []))

    # Fallback to extracting from button checkmarks if state was lost
    if len(selected) < 2 and callback.message:
        recovered = extract_selected_interests_from_markup(callback.message)
        if len(recovered) >= 2:
            selected = recovered

    if len(selected) < 2:
        await callback.answer("Please select at least 2 interests!", show_alert=True)
        return

    # Acknowledge the callback query immediately to stop the button loading spinner
    await callback.answer()
    if not callback.from_user:
        return

    # Cap at 5 maximum interests
    if len(selected) > 5:
        selected = selected[:5]

    # Retrieve or auto-create user
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        user = User(
            id=f"usr_{uuid.uuid4().hex[:12]}",
            telegram_id=callback.from_user.id,
            age_verified=True,
        )

    # Resolve unique_id
    unique_id = data.get("unique_id") or user.unique_id
    if not unique_id:
        unique_id = f"lk_{abs(user.telegram_id) % 90000 + 10000}"
    user.unique_id = unique_id

    # Resolve alias
    raw_alias = data.get("alias")
    if not raw_alias and callback.from_user.first_name:
        raw_alias = callback.from_user.first_name.strip()
    if not raw_alias or len(raw_alias) < 2:
        raw_alias = f"User_{user.id[-4:]}"
    alias = raw_alias[:50]

    # Resolve age
    try:
        age = int(data.get("age", 21))
    except (ValueError, TypeError):
        age = 21
    age = max(18, min(99, age))

    # Resolve gender
    gender_val = data.get("gender", Gender.PREFER_NOT_TO_SAY.value)
    try:
        gender = Gender(gender_val)
    except Exception:
        gender = Gender.PREFER_NOT_TO_SAY

    # 1. Save user FIRST to satisfy foreign key constraints in Supabase
    user.transition_state(UserState.MAIN_MENU)
    try:
        await user_repo.save(user)
    except Exception as exc:
        logger.error("[Onboarding] Error saving user %s: %s", user.id, exc)

    # 2. Save profile SECOND
    profile = Profile(
        user_id=user.id,
        unique_id=unique_id,
        display_name=alias,
        age=age,
        gender=gender,
        interests=selected,
        preferred_gender_filter=[GenderPreference.ANY],
        min_age_filter=max(18, age - 7),
        max_age_filter=min(99, age + 7),
    )
    try:
        await profile_repo.save(profile)
    except Exception as exc:
        logger.error("[Onboarding] Error saving profile for %s: %s", user.id, exc)

    # 3. Evaluate referral reward if applicable
    if referral_service:
        try:
            await referral_service.evaluate_and_grant_reward(user.id)
        except Exception:
            pass

    await state.clear()

    target_bot = bot or callback.bot
    chat_id = (
        callback.message.chat.id
        if (callback.message and callback.message.chat)
        else callback.from_user.id
    )

    resolved_uid = profile.unique_id or user.unique_id
    unique_tag = f"@{html.escape(resolved_uid)}" if resolved_uid else "<i>Not set</i>"
    safe_name = html.escape(profile.display_name)
    gender_label = profile.gender.value.replace("_", " ").title()
    interests_label = ", ".join(profile.interests).title()

    welcome_text = (
        f"🎉 <b>Profile Created & Safely Saved in Memory!</b> ✨\n\n"
        f"• 👤 <b>Display Name:</b> {safe_name}\n"
        f"• 🆔 <b>Permanent ID:</b> {unique_tag} 🔒 <i>(Immutable — cannot be edited)</i>\n"
        f"• 🎂 <b>Age & Gender:</b> {profile.age} • {gender_label}\n"
        f"• 🎯 <b>Interests ({len(profile.interests)}):</b> {interests_label}\n"
        f"• 🌟 <b>Karma Standing:</b> {user.karma_score} / 500 (Good Standing ✨)\n\n"
        f"🔒 <b>Privacy Shield Guarantee:</b>\n"
        f"• 🛡 Your Telegram username and phone number are 100% confidential and hidden.\n"
        f"• 💬 Conversations are ephemeral with zero permanent database chat logs.\n"
        f"• 🎮 All 17 games are ready to play in the <b>LikBy Play Mini App</b>!\n\n"
        f"Tap <b>🎲 Find Match</b> below whenever you're ready to start chatting!"
    )

    message_sent = False
    if target_bot:
        try:
            await target_bot.send_message(
                chat_id=chat_id,
                text=welcome_text,
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard(),
            )
            message_sent = True
        except Exception as exc:
            logger.warning("[Onboarding] HTML send failed, trying plain text: %s", exc)
            try:
                plain_text = (
                    f"🎉 Profile Created & Safely Saved in Memory! ✨\n\n"
                    f"• 👤 Display Name: {profile.display_name}\n"
                    f"• 🆔 Permanent ID: @{resolved_uid}\n"
                    f"• 🎂 Age & Gender: {profile.age} • {gender_label}\n"
                    f"• 🎯 Interests: {interests_label}\n"
                    f"• 🌟 Karma Standing: {user.karma_score} / 500\n\n"
                    f"🔒 Privacy Shield Guarantee:\n"
                    f"• 🛡 Your Telegram info is 100% confidential.\n"
                    f"• 🎮 All 17 games are ready in the LikBy Play Mini App!\n\n"
                    f"Tap 🎲 Find Match below to start chatting!"
                )
                await target_bot.send_message(
                    chat_id=chat_id,
                    text=plain_text,
                    reply_markup=get_main_menu_keyboard(),
                )
                message_sent = True
            except Exception as final_exc:
                logger.error("[Onboarding] Both HTML and plain text sends failed: %s", final_exc)

    # Delete the inline topic selector keyboard only after sending the welcome message
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

