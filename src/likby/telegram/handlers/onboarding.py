"""
likby.telegram.handlers.onboarding
Onboarding FSM handlers: Alias, Age, Gender, and Interests selection.
"""

import re
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from likby.domain.entities.profile import Profile
from likby.domain.enums import Gender, GenderPreference, UserState
from likby.repositories.interfaces import ProfileRepository, UserRepository
from likby.telegram.keyboards import (
    get_gender_keyboard,
    get_interests_keyboard,
    get_main_menu_keyboard,
)
from likby.telegram.states import OnboardingStates
from likby.telegram.utils import safe_edit_reply_markup, safe_edit_text

router = Router(name="onboarding")

UNIQUE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,20}$")


@router.message(OnboardingStates.waiting_for_alias)
async def process_alias(message: Message, state: FSMContext) -> None:
    alias = (message.text or "").strip()
    if len(alias) < 2 or len(alias) > 30:
        await message.answer(
            "⚠️ Name must be between 2 and 30 characters. Please choose a different name:"
        )
        return

    await state.update_data(alias=alias)
    await state.set_state(OnboardingStates.waiting_for_unique_id)
    await message.answer(
        f"Nice to meet you, <b>{alias}</b>! ✨\n\n"
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
    clean_id = raw_id.lstrip("@").lower()

    if not UNIQUE_ID_REGEX.match(clean_id):
        await message.answer(
            "⚠️ <b>Invalid Unique ID format.</b>\n\n"
            "• Must be 3 to 20 characters long\n"
            "• Only letters (a-z), numbers (0-9), and underscores (_)\n"
            "• Example: <code>alex_99</code> or <code>sam2024</code>\n\n"
            "Please choose a valid Unique ID:",
            parse_mode="HTML",
        )
        return

    # Check case-insensitive uniqueness in database
    existing_user = await user_repo.get_by_unique_id(clean_id)
    if existing_user:
        await message.answer(
            f"⚠️ <b>@{clean_id} is already taken!</b>\n\n"
            "Another user has already claimed this Unique ID. Please choose a different handle:",
            parse_mode="HTML",
        )
        return

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
        await message.answer("⚠️ Please enter your age as a whole number (e.g. 25):")
        return

    age = int(text)
    if age < 18 or age > 120:
        await message.answer("⚠️ You must be at least 18 years old to use LikBy:")
        return

    await state.update_data(age=age)
    await state.set_state(OnboardingStates.waiting_for_gender)
    await message.answer(
        "⚧ <b>Select your gender identity:</b>",
        parse_mode="HTML",
        reply_markup=get_gender_keyboard(),
    )


@router.callback_query(OnboardingStates.waiting_for_gender, F.data.startswith("gender:"))
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


@router.callback_query(OnboardingStates.waiting_for_interests, F.data.startswith("interest_toggle:"))
async def toggle_interest(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    interest_code = callback.data.split(":")[1]
    data = await state.get_data()
    selected = list(data.get("selected_interests", []))

    if interest_code in selected:
        selected.remove(interest_code)
        await callback.answer()
    else:
        if len(selected) >= 5:
            await callback.answer("You can select up to 5 interests maximum!", show_alert=True)
            return
        selected.append(interest_code)
        await callback.answer()

    await state.update_data(selected_interests=selected)
    await safe_edit_reply_markup(
        callback.message,
        reply_markup=get_interests_keyboard(selected=selected),
    )


@router.callback_query(OnboardingStates.waiting_for_interests, F.data == "interest_done")
async def finish_interests(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    data = await state.get_data()
    selected = list(data.get("selected_interests", []))

    if len(selected) < 2:
        await callback.answer("Please select at least 2 interests!", show_alert=True)
        return

    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return

    unique_id = data.get("unique_id")
    if unique_id:
        user.unique_id = unique_id

    profile = Profile(
        user_id=user.id,
        unique_id=unique_id,
        display_name=data["alias"],
        age=data["age"],
        gender=Gender(data["gender"]),
        interests=selected,
        preferred_gender_filter=[GenderPreference.ANY],
        min_age_filter=max(18, data["age"] - 7),
        max_age_filter=min(99, data["age"] + 7),
    )
    await profile_repo.save(profile)

    user.transition_state(UserState.MAIN_MENU)
    await user_repo.save(user)
    await state.clear()

    await callback.message.delete()
    unique_tag = f"@{profile.unique_id}" if profile.unique_id else "<i>Not set</i>"
    await callback.message.answer(
        f"🎉 <b>Profile created successfully!</b>\n\n"
        f"• <b>Name:</b> {profile.display_name} <i>(non-unique)</i>\n"
        f"• <b>Unique ID:</b> {unique_tag} 🔒 <i>(Permanent — cannot be edited)</i>\n"
        f"• <b>Age:</b> {profile.age}\n"
        f"• <b>Interests:</b> {', '.join(profile.interests).title()}\n\n"
        "Tap <b>🎲 Find a Match</b> below whenever you're ready to start chatting!",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )
