"""
tikible.telegram.handlers.onboarding
Onboarding FSM handlers: Alias, Age, Gender, and Interests selection.
"""

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from tikible.domain.entities.profile import Profile
from tikible.domain.enums import Gender, GenderPreference, UserState
from tikible.repositories.interfaces import ProfileRepository, UserRepository
from tikible.telegram.keyboards import (
    get_gender_keyboard,
    get_interests_keyboard,
    get_main_menu_keyboard,
)
from tikible.telegram.states import OnboardingStates
from tikible.telegram.utils import safe_edit_reply_markup, safe_edit_text

router = Router(name="onboarding")


@router.message(OnboardingStates.waiting_for_alias)
async def process_alias(message: Message, state: FSMContext) -> None:
    alias = (message.text or "").strip()
    if len(alias) < 2 or len(alias) > 30:
        await message.answer(
            "⚠️ Alias must be between 2 and 30 characters. Please choose a different name:"
        )
        return

    await state.update_data(alias=alias)
    await state.set_state(OnboardingStates.waiting_for_age)
    await message.answer(
        f"Nice to meet you, <b>{alias}</b>! ✨\n\n"
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

    profile = Profile(
        user_id=user.id,
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
    await callback.message.answer(
        f"🎉 <b>Profile created successfully!</b>\n\n"
        f"Alias: <b>{profile.display_name}</b>\n"
        f"Age: <b>{profile.age}</b>\n"
        f"Interests: <b>{', '.join(profile.interests).title()}</b>\n\n"
        "Tap <b>🎲 Find a Match</b> below whenever you're ready to start chatting!",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )
