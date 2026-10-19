"""
likby.telegram.handlers.menu
Authoritative handlers for LikBy Navigation Hubs:
- 👤 Profile & VIP Hub (Profile, Karma, Settings, VIP Plans, Safety)
- 👥 Connections Hub (Friends, Requests, Who Liked Me, ID Search, Referrals)
- 💬 My Chats Hub (Active conversation controls, instant matchmaking, transcripts)
"""

from datetime import date, datetime, timezone
import re
from typing import Optional, Sequence
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from likby.domain.enums import Gender, GenderPreference
from likby.repositories.interfaces import (
    ChatSessionRepository,
    ProfileRepository,
    UserRepository,
)
from likby.services.discovery_service import DiscoveryService
from likby.services.karma_service import KarmaService
from likby.services.social_service import SocialService
from likby.services.subscription_service import SubscriptionService
from likby.telegram.keyboards import (
    AVAILABLE_INTERESTS,
    AVAILABLE_LANGUAGES,
    get_chat_hub_keyboard,
    get_connections_hub_keyboard,
    get_interests_keyboard,
    get_languages_keyboard,
    get_main_menu_keyboard,
    get_preferred_gender_keyboard,
    get_profile_edit_menu_keyboard,
    get_profile_interests_keyboard,
    get_profile_vip_keyboard,
    get_relationship_intent_keyboard,
)
from likby.telegram.states import EditProfileStates, SearchStates
from likby.telegram.utils import safe_edit_reply_markup, safe_edit_text

router = Router(name="menu")



async def send_or_edit(
    event: Message | CallbackQuery,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    """Helper to send a new message or cleanly edit an existing inline card in-place."""
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await safe_edit_text(
                event.message,
                text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
    else:
        await event.answer(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )


def parse_date_of_birth(raw: str) -> Optional[date]:
    """Parse DOB from flexible formats: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, YYYY/MM/DD, DD.MM.YYYY."""
    clean = raw.strip()
    patterns = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"]
    for pat in patterns:
        try:
            return datetime.strptime(clean, pat).date()
        except ValueError:
            continue
    return None


def parse_location_input(raw: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse user location string into (city, state, country)."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) >= 3:
        return parts[0][:100], parts[1][:100], parts[2][:60]
    elif len(parts) == 2:
        return parts[0][:100], None, parts[1][:60]
    elif len(parts) == 1:
        return parts[0][:100], None, None
    return None, None, None


# ==============================================================================
# 1. 👤 Profile & VIP Hub
# ==============================================================================

@router.message(F.text.in_(["👤 Profile & VIP", "👤 My Profile", "👤 Profile", "👤 Account"]))
@router.message(Command("profile"))
@router.message(Command("account"))
@router.callback_query(F.data == "vip:hub")
async def show_profile_vip_hub(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
    subscription_service: SubscriptionService,
    social_service: SocialService,
) -> None:
    """Consolidated Profile & VIP Membership Hub."""
    user_tg = event.from_user
    if not user_tg:
        return

    tg_id = user_tg.id
    user = await user_repo.get_by_telegram_id(tg_id)
    if not user:
        if isinstance(event, Message):
            await event.answer("Please type /start to create your profile.")
        else:
            await event.answer("Please type /start to create your profile.", show_alert=True)
        return

    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        if isinstance(event, Message):
            await event.answer("Please type /start to complete your profile.")
        else:
            await event.answer("Please type /start to complete your profile.", show_alert=True)
        return

    limits = await subscription_service.get_plan_limits(user.id)
    friends = await social_service.get_user_friends(user.id)

    tier_name = limits.get("display_name", limits.get("tier", "Base")).upper()
    unique_tag = f"@{user.unique_id or profile.unique_id}" if (user.unique_id or profile.unique_id) else "<i>Not set</i>"
    interests_str = ", ".join(profile.interests).title() if profile.interests else "<i>None selected</i>"
    gender_str = profile.gender.value.replace("_", " ").title()

    # DOB and age
    dob_str = profile.dob.strftime("%d %B %Y") if profile.dob else "<i>Not set</i>"

    # Preferred matching gender
    pref_parts = [p.value.replace("_", " ").title() for p in profile.preferred_gender_filter]
    pref_gender_str = ", ".join(pref_parts) if pref_parts else "Any"

    # Location
    loc_parts = [p for p in (profile.location_city, profile.location_state, profile.location_country) if p]
    location_str = ", ".join(loc_parts) if loc_parts else "<i>Not set</i>"

    # Languages
    languages_str = ", ".join(l.upper() for l in profile.languages) if profile.languages else "EN"

    # Intent
    intent_str = profile.relationship_intent or "<i>Not specified</i>"

    # Bio
    bio_str = f"<i>\"{profile.bio}\"</i>" if profile.bio else "<i>No bio yet — tap Edit Profile Details to add one!</i>"

    # Dynamic Karma Status Badge
    karma = user.karma_score
    if karma >= 250:
        karma_badge = "Elite Match Priority 🌟"
    elif karma >= 100:
        karma_badge = "Trusted Member ✨"
    else:
        karma_badge = "Good Standing"

    text = (
        f"👤 <b>LikBy Profile & VIP Membership</b>\n\n"
        f"• <b>Display Name:</b> {profile.display_name}\n"
        f"• <b>Permanent ID:</b> {unique_tag} 🔒 <i>(Immutable)</i>\n"
        f"• <b>Age & DOB:</b> {profile.age} yrs • DOB: {dob_str}\n"
        f"• <b>Gender:</b> {gender_str} • <b>Looking For:</b> {intent_str}\n"
        f"• <b>Matching Filter:</b> {pref_gender_str}\n"
        f"• <b>Location:</b> {location_str}\n"
        f"• <b>Languages:</b> {languages_str}\n"
        f"• <b>Bio:</b> {bio_str}\n"
        f"• <b>Interests:</b> {interests_str}\n"
        f"• <b>Karma Reputation:</b> {karma} / 500 ({karma_badge})\n\n"
        f"👑 <b>Current Tier:</b> <b>{tier_name}</b>\n"
        f"• <b>Friends Quota:</b> {len(friends)} / {limits['max_friends']} slots used\n"
        f"• <b>Daily Searches:</b> {limits['daily_searches_limit']} / day\n"
        f"• <b>Daily Duels:</b> {limits.get('daily_duel_limit', 5)} / day\n\n"
        f"<i>🔒 Your Telegram username and phone number are never shared.</i>"
    )

    await send_or_edit(
        event,
        text,
        reply_markup=get_profile_vip_keyboard(tier_code=limits.get("tier", "BASE")),
    )


# ------------------------------------------------------------------------------
# Profile Edit Submenu & Handlers
# ------------------------------------------------------------------------------

async def render_profile_edit_menu(
    message: Optional[Message],
    tg_id: int,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Render the profile edit menu in-place."""
    if not message:
        return
    user = await user_repo.get_by_telegram_id(tg_id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    dob_str = profile.dob.strftime("%d %B %Y") if profile.dob else "Not set"
    loc_parts = [p for p in (profile.location_city, profile.location_state, profile.location_country) if p]
    location_str = ", ".join(loc_parts) if loc_parts else "Not set"
    languages_str = ", ".join(l.upper() for l in profile.languages) if profile.languages else "EN"
    pref_parts = [p.value.replace("_", " ").title() for p in profile.preferred_gender_filter]
    pref_str = ", ".join(pref_parts) if pref_parts else "Any"
    intent_str = profile.relationship_intent or "Not set"
    bio_str = f"\"{profile.bio}\"" if profile.bio else "Not set"

    text = (
        f"⚙️ <b>Edit Profile Details</b>\n\n"
        f"Select an item to update your profile information:\n\n"
        f"• <b>Display Name:</b> {profile.display_name}\n"
        f"• <b>Bio:</b> {bio_str}\n"
        f"• <b>Date of Birth:</b> {dob_str} <i>(Age: {profile.age})</i>\n"
        f"• <b>Location:</b> {location_str}\n"
        f"• <b>Looking For:</b> {intent_str}\n"
        f"• <b>Matching Filter:</b> {pref_str}\n"
        f"• <b>Languages:</b> {languages_str}\n"
        f"• <b>Interests:</b> {', '.join(profile.interests).title() if profile.interests else 'None'}\n"
    )

    await safe_edit_text(
        message,
        text,
        parse_mode="HTML",
        reply_markup=get_profile_edit_menu_keyboard(),
    )


@router.callback_query(F.data == "profile:edit_menu")
async def show_profile_edit_menu(
    callback: CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Submenu for viewing and editing individual profile details."""
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    await render_profile_edit_menu(callback.message, callback.from_user.id, user_repo, profile_repo)



@router.callback_query(F.data == "profile:edit_name")
async def start_edit_name(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Prompt user to change their display name."""
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

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Back to Edit Menu", callback_data="profile:edit_menu")]
        ]
    )

    await callback.message.answer(
        f"✏️ <b>Change Display Name</b>\n\n"
        f"Current Name: <b>{profile.display_name}</b>\n"
        f"Unique ID: <b>{unique_tag}</b> 🔒 <i>(Permanent — cannot be edited)</i>\n\n"
        f"Please send your new display name (2-30 characters):\n"
        f"<i>(Type /cancel to abort.)</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb,
    )


@router.message(EditProfileStates.waiting_for_new_name)
async def process_new_name(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Validate and persist new display name."""
    raw_text = (message.text or "").strip()
    if raw_text == "/cancel":
        await state.clear()
        cancel_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Return to Profile Hub", callback_data="vip:hub")]
            ]
        )
        await message.answer("Display name change cancelled.", reply_markup=cancel_kb)
        return

    if len(raw_text) < 2 or len(raw_text) > 30:
        await message.answer(
            "⚠️ Display name must be between 2 and 30 characters. Please try again (or /cancel):"
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

    profile.update_display_name(raw_text)
    await profile_repo.save(profile)
    await state.clear()

    unique_tag = f"@{user.unique_id or profile.unique_id}" if (user.unique_id or profile.unique_id) else "Not set"
    done_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Return to Profile Hub", callback_data="vip:hub")]
        ]
    )
    await message.answer(
        f"✅ <b>Display Name Updated!</b>\n\n"
        f"• <b>New Name:</b> {profile.display_name}\n"
        f"• <b>Unique ID:</b> {unique_tag} 🔒",
        parse_mode="HTML",
        reply_markup=done_kb,
    )


@router.callback_query(F.data == "profile:edit_bio")
async def start_edit_bio(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Prompt user to set or update their bio."""
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    await state.set_state(EditProfileStates.waiting_for_bio)
    current_bio = f"<i>\"{profile.bio}\"</i>" if profile.bio else "<i>None</i>"

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Back to Edit Menu", callback_data="profile:edit_menu")]
        ]
    )

    await callback.message.answer(
        f"📝 <b>Edit Personal Bio</b>\n\n"
        f"Current Bio: {current_bio}\n\n"
        f"Please send your new bio (up to 500 characters).\n"
        f"<i>(Send 'clear' to remove your bio, or /cancel to abort.)</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb,
    )


@router.message(EditProfileStates.waiting_for_bio)
async def process_new_bio(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Validate and persist new bio."""
    raw_text = (message.text or "").strip()
    if raw_text == "/cancel":
        await state.clear()
        cancel_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Return to Profile Hub", callback_data="vip:hub")]
            ]
        )
        await message.answer("Bio update cancelled.", reply_markup=cancel_kb)
        return

    if not message.from_user:
        return

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        return

    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    if raw_text.lower() == "clear":
        profile.update_bio(None)
    else:
        if len(raw_text) > 500:
            await message.answer("⚠️ Bio cannot exceed 500 characters. Please shorten your message (or /cancel):")
            return
        profile.update_bio(raw_text)

    await profile_repo.save(profile)
    await state.clear()

    done_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Return to Profile Hub", callback_data="vip:hub")]
        ]
    )
    status_str = "cleared" if not profile.bio else f"updated to: <i>\"{profile.bio}\"</i>"
    await message.answer(
        f"✅ <b>Bio Updated!</b>\n\nYour personal bio is now {status_str}.",
        parse_mode="HTML",
        reply_markup=done_kb,
    )


@router.callback_query(F.data == "profile:edit_dob")
async def start_edit_dob(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Prompt user to set their date of birth."""
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    await state.set_state(EditProfileStates.waiting_for_dob)
    current_dob = profile.dob.strftime("%d %B %Y") if profile.dob else "Not set"

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Back to Edit Menu", callback_data="profile:edit_menu")]
        ]
    )

    await callback.message.answer(
        f"🎂 <b>Set Date of Birth</b>\n\n"
        f"Current DOB: <b>{current_dob}</b> <i>(Current age: {profile.age})</i>\n\n"
        f"Please enter your Date of Birth in <code>YYYY-MM-DD</code> or <code>DD/MM/YYYY</code> format:\n"
        f"<i>(Example: <code>2000-05-15</code> or <code>15/05/2000</code>. Type /cancel to abort.)</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb,
    )


@router.message(EditProfileStates.waiting_for_dob)
async def process_new_dob(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Validate and persist date of birth and derived age."""
    raw_text = (message.text or "").strip()
    if raw_text == "/cancel":
        await state.clear()
        cancel_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Return to Profile Hub", callback_data="vip:hub")]
            ]
        )
        await message.answer("Date of birth change cancelled.", reply_markup=cancel_kb)
        return

    parsed_date = parse_date_of_birth(raw_text)
    if not parsed_date:
        await message.answer(
            "⚠️ <b>Invalid date format.</b>\n\n"
            "Please use <code>YYYY-MM-DD</code> or <code>DD/MM/YYYY</code> format (e.g. <code>2001-08-20</code> or <code>20/08/2001</code>):\n"
            "<i>(Type /cancel to abort.)</i>",
            parse_mode="HTML",
        )
        return

    today = datetime.now(timezone.utc).date()
    if parsed_date > today:
        await message.answer("⚠️ Date of birth cannot be in the future. Please try again (or /cancel):")
        return

    calc_age = today.year - parsed_date.year - ((today.month, today.day) < (parsed_date.month, parsed_date.day))
    if calc_age < 18:
        await message.answer(
            "🛑 <b>Age Restriction:</b> LikBy is strictly for users 18 years or older. "
            "Please enter a valid adult date of birth (or /cancel):"
        )
        return
    if calc_age > 120:
        await message.answer("⚠️ Please enter a realistic date of birth (or /cancel):")
        return

    if not message.from_user:
        return
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    profile.set_dob(parsed_date)
    await profile_repo.save(profile)
    await state.clear()

    done_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Return to Profile Hub", callback_data="vip:hub")]
        ]
    )
    await message.answer(
        f"✅ <b>Date of Birth Updated!</b>\n\n"
        f"• <b>DOB:</b> {parsed_date.strftime('%d %B %Y')}\n"
        f"• <b>Verified Age:</b> {profile.age} years old 🎂",
        parse_mode="HTML",
        reply_markup=done_kb,
    )


@router.callback_query(F.data == "profile:edit_location")
async def start_edit_location(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Prompt user to set their location."""
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    await state.set_state(EditProfileStates.waiting_for_location)
    loc_parts = [p for p in (profile.location_city, profile.location_state, profile.location_country) if p]
    current_loc = ", ".join(loc_parts) if loc_parts else "Not set"

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Back to Edit Menu", callback_data="profile:edit_menu")]
        ]
    )

    await callback.message.answer(
        f"📍 <b>Set Location</b>\n\n"
        f"Current Location: <b>{current_loc}</b>\n\n"
        f"Please enter your <code>City, State, Country</code> (e.g. <code>San Francisco, California, United States</code> or <code>Mumbai, Maharashtra, India</code> or <code>London, UK</code>):\n"
        f"<i>(Send 'clear' to reset location, or /cancel to abort.)</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb,
    )


@router.message(EditProfileStates.waiting_for_location)
async def process_new_location(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Validate and persist geographic location."""
    raw_text = (message.text or "").strip()
    if raw_text == "/cancel":
        await state.clear()
        cancel_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Return to Profile Hub", callback_data="vip:hub")]
            ]
        )
        await message.answer("Location update cancelled.", reply_markup=cancel_kb)
        return

    if not message.from_user:
        return
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    if raw_text.lower() == "clear":
        profile.update_location(country=None, state=None, city=None)
    else:
        city, state_name, country = parse_location_input(raw_text)
        profile.update_location(country=country, state=state_name, city=city)

    await profile_repo.save(profile)
    await state.clear()

    loc_parts = [p for p in (profile.location_city, profile.location_state, profile.location_country) if p]
    loc_display = ", ".join(loc_parts) if loc_parts else "Cleared"

    done_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Return to Profile Hub", callback_data="vip:hub")]
        ]
    )
    await message.answer(
        f"✅ <b>Location Updated!</b>\n\n"
        f"• <b>Current Location:</b> {loc_display} 📍",
        parse_mode="HTML",
        reply_markup=done_kb,
    )


@router.callback_query(F.data == "profile:edit_intent")
async def show_edit_intent(
    callback: CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Display relationship / social intent selector."""
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    await safe_edit_text(
        callback.message,
        "💘 <b>What are you looking for on LikBy?</b>\n\n"
        "Select your primary intent to help match you with like-minded people:",
        parse_mode="HTML",
        reply_markup=get_relationship_intent_keyboard(current_intent=profile.relationship_intent),
    )


@router.callback_query(F.data.startswith("intent:"))
async def set_relationship_intent(
    callback: CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Save selected relationship / social intent."""
    intent_val = callback.data.split(":", 1)[1]
    if not callback.from_user or not callback.message:
        return
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    profile.update_relationship_intent(intent_val)
    await profile_repo.save(profile)
    await callback.answer(f"Updated looking for to: {intent_val}! ✨")

    await safe_edit_reply_markup(
        callback.message,
        reply_markup=get_relationship_intent_keyboard(current_intent=profile.relationship_intent),
    )


@router.callback_query(F.data == "profile:edit_pref_gender")
async def show_edit_pref_gender(
    callback: CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Display matching partner gender filter selector."""
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    current = [p.value for p in profile.preferred_gender_filter]
    await safe_edit_text(
        callback.message,
        "⚧ <b>Preferred Partner Matching Gender:</b>\n\n"
        "Choose who you would like to be matched with during discovery:",
        parse_mode="HTML",
        reply_markup=get_preferred_gender_keyboard(current_pref=current),
    )


@router.callback_query(F.data.startswith("pref_gender:"))
async def set_preferred_gender(
    callback: CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Update partner matching gender preference filter."""
    gender_code = callback.data.split(":", 1)[1]
    if not callback.from_user or not callback.message:
        return
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    try:
        pref_enum = GenderPreference(gender_code)
    except Exception:
        pref_enum = GenderPreference.ANY

    profile.update_preferences(preferred_gender=[pref_enum])
    await profile_repo.save(profile)
    await callback.answer(f"Matching preference updated to: {gender_code.replace('_', ' ').title()}! ✨")

    await safe_edit_reply_markup(
        callback.message,
        reply_markup=get_preferred_gender_keyboard(current_pref=[pref_enum.value]),
    )


@router.callback_query(F.data == "profile:edit_languages")
async def show_edit_languages(
    callback: CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Display language multi-select matrix."""
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    await safe_edit_text(
        callback.message,
        "🌐 <b>Select Spoken Languages</b>\n\n"
        "Tap languages to select or deselect, then press Save:",
        parse_mode="HTML",
        reply_markup=get_languages_keyboard(selected=profile.languages),
    )


@router.callback_query(F.data.startswith("lang_toggle:"))
async def toggle_language(
    callback: CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Toggle language selection for user profile."""
    lang_code = callback.data.split(":", 1)[1].lower()
    if not callback.from_user or not callback.message:
        return
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    current = list(profile.languages)
    if lang_code in current:
        if len(current) <= 1:
            await callback.answer("You must select at least 1 language!", show_alert=True)
            return
        current.remove(lang_code)
    else:
        current.append(lang_code)

    profile.update_languages(current)
    await profile_repo.save(profile)
    await callback.answer()

    await safe_edit_reply_markup(
        callback.message,
        reply_markup=get_languages_keyboard(selected=profile.languages),
    )


@router.callback_query(F.data == "lang_done")
async def finish_languages(
    callback: CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Acknowledge language save and return to edit menu."""
    await callback.answer("Languages saved successfully! ✨")
    if callback.from_user:
        await render_profile_edit_menu(callback.message, callback.from_user.id, user_repo, profile_repo)



@router.callback_query(F.data == "profile:edit_interests")
async def show_edit_interests(
    callback: CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Display interest multi-select matrix for profile."""
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    await safe_edit_text(
        callback.message,
        "🎯 <b>Select Topics & Interests</b>\n\n"
        "Tap to select 2 to 5 topics you enjoy discussing:",
        parse_mode="HTML",
        reply_markup=get_profile_interests_keyboard(selected=profile.interests),
    )


@router.callback_query(F.data.startswith("prof_interest_toggle:"))
async def toggle_profile_interest(
    callback: CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Toggle interest code in profile."""
    code = callback.data.split(":", 1)[1].lower()
    if not callback.from_user or not callback.message:
        return
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    selected = list(profile.interests)
    if code in selected:
        selected.remove(code)
    else:
        if len(selected) >= 5:
            await callback.answer("Maximum 5 interests allowed! Tap Save when finished.", show_alert=True)
            return
        selected.append(code)

    profile.interests = selected
    profile.updated_at = datetime.now(timezone.utc)
    await profile_repo.save(profile)
    await callback.answer()

    await safe_edit_reply_markup(
        callback.message,
        reply_markup=get_profile_interests_keyboard(selected=profile.interests),
    )


@router.callback_query(F.data == "prof_interest_done")
async def finish_profile_interests(
    callback: CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
) -> None:
    """Verify minimum 2 interests and return to edit menu."""
    if not callback.from_user:
        return
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return
    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return

    if len(profile.interests) < 2:
        await callback.answer("Please select at least 2 interests!", show_alert=True)
        return

    await callback.answer("Interests saved successfully! ✨")
    await render_profile_edit_menu(callback.message, callback.from_user.id, user_repo, profile_repo)




# ==============================================================================
# 2. 🌟 My Karma & Reputation
# ==============================================================================

@router.message(F.text == "🌟 My Karma")
@router.message(Command("karma"))
@router.callback_query(F.data == "vip:karma")
async def show_karma(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    karma_service: KarmaService,
) -> None:
    """Displays user reputation score and recent activity ledger."""
    user_tg = event.from_user
    if not user_tg:
        return

    user = await user_repo.get_by_telegram_id(user_tg.id)
    if not user:
        if isinstance(event, Message):
            await event.answer("Please type /start first.")
        else:
            await event.answer("Please type /start first.", show_alert=True)
        return

    summary = await karma_service.get_user_karma_summary(user.id)
    score = summary["karma_score"]
    ledger = summary["ledger"]

    history_text = ""
    if ledger:
        history_text = "\n\n<b>Recent Karma Activity:</b>\n"
        for item in ledger[:5]:
            delta_prefix = f"+{item['delta']}" if item["delta"] > 0 else str(item["delta"])
            history_text += f"• {item['source']}: <b>{delta_prefix}</b> <i>({item['created_at'][:10]})</i>\n"
    else:
        history_text = "\n\n<i>No recent karma adjustments recorded.</i>"

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Back to Profile Hub", callback_data="vip:hub")]
        ]
    )

    text = (
        f"🌟 <b>Your LikBy Karma & Reputation</b>\n\n"
        f"Current Karma Score: <b>{score}</b> / 500\n\n"
        f"<b>How Karma Works:</b>\n"
        f"• Good chat rating (👍): <b>+1</b>\n"
        f"• Disliked chat rating (👎): <b>-1</b>\n"
        f"• Higher scores build faster matchmaking and elite priority!"
        f"{history_text}"
    )

    await send_or_edit(event, text, reply_markup=back_kb)


# ==============================================================================
# 3. 🛡 Help & Safety Guidelines
# ==============================================================================

@router.message(F.text.in_(["🛡 Help & Safety", "📜 Guidelines"]))
@router.message(Command("guidelines"))
@router.message(Command("help"))
@router.message(Command("safety"))
@router.callback_query(F.data == "vip:safety")
async def show_help_and_safety(event: Message | CallbackQuery) -> None:
    """Presents platform safety standards, zero ads policy, and guidelines."""
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Back to Profile Hub", callback_data="vip:hub")]
        ]
    )

    text = (
        "🛡️ <b>LikBy Safety & Community Guidelines</b>\n\n"
        "LikBy is built on privacy, mutual respect, and safe discovery.\n\n"
        "<b>Core Principles:</b>\n"
        "1. <b>Strict Anonymity:</b> Your Telegram account, phone number, and location are never revealed.\n"
        "2. <b>Zero Tolerance:</b> Harassment, hate speech, and spam result in immediate suspension.\n"
        "3. <b>Adults Only (18+):</b> Users must be 18 or older.\n"
        "4. <b>Safety Controls:</b> You can tap <b>⚠️ Report</b> during any chat to instantly disconnect and permanently block a partner.\n"
        "5. <b>Content Protection:</b> Outbound media is protected with Telegram Content Protection to deter saving and forwarding.\n"
        "6. <b>Zero-Advertising Policy:</b> LikBy is 100% advertisement-free. We never show sponsored ads or third-party promotional broadcasts.\n"
        "7. <b>Permanent Persistence:</b> LikBy does not employ disappearing or view-once timers.\n\n"
        "<b>Media Allowance:</b> Check your daily quota anytime with /my_media_usage.\n"
        "<b>Need help?</b> Contact LikBy Support anytime via /support."
    )

    await send_or_edit(event, text, reply_markup=back_kb)


# ==============================================================================
# 4. 👥 Connections & Social Hub
# ==============================================================================

@router.message(F.text.in_(["👥 Connections", "👥 Social", "👥 Friends & Social"]))
@router.message(Command("connections"))
@router.message(Command("social"))
@router.callback_query(F.data == "conn:hub")
async def show_connections_hub(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
    social_service: SocialService,
    discovery_service: DiscoveryService,
    subscription_service: SubscriptionService,
) -> None:
    """Consolidated interactive Social & Connections Hub."""
    user_tg = event.from_user
    if not user_tg:
        return

    user = await user_repo.get_by_telegram_id(user_tg.id)
    if not user:
        if isinstance(event, Message):
            await event.answer("Please type /start first.")
        else:
            await event.answer("Please type /start first.", show_alert=True)
        return

    profile = await profile_repo.get_by_user_id(user.id)
    unique_tag = f"@{user.unique_id or (profile.unique_id if profile else '')}" if (user.unique_id or (profile and profile.unique_id)) else "Not set"

    friends = await social_service.get_user_friends(user.id)
    reqs = await discovery_service.get_incoming_requests(user.id)
    likes = await social_service.get_who_liked_me(user.id)
    limits = await subscription_service.get_plan_limits(user.id)

    text = (
        f"👥 <b>Connections & Social Hub</b>\n\n"
        f"Manage your private network, friend requests, and admirers:\n\n"
        f"• <b>My Friends:</b> <b>{len(friends)} / {limits['max_friends']}</b> slots used\n"
        f"• <b>Incoming Requests:</b> <b>{len(reqs)}</b> waiting\n"
        f"• <b>Who Liked You:</b> <b>{len(likes)}</b> admirers ✨\n"
        f"• <b>Your Unique Handle:</b> <code>{unique_tag}</code>\n\n"
        f"<i>Select an option below to explore your connections:</i>"
    )

    kb = get_connections_hub_keyboard(
        friends_count=len(friends),
        requests_count=len(reqs),
        likes_count=len(likes),
    )

    await send_or_edit(event, text, reply_markup=kb)


@router.message(F.text == "👥 My Friends")
@router.message(Command("friends"))
@router.callback_query(F.data == "conn:friends")
async def show_friends(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    social_service: SocialService,
    subscription_service: SubscriptionService,
) -> None:
    """Displays friends list with removal actions and Back to Connections button."""
    user_tg = event.from_user
    if not user_tg:
        return

    user = await user_repo.get_by_telegram_id(user_tg.id)
    if not user:
        if isinstance(event, Message):
            await event.answer("Please type /start first.")
        else:
            await event.answer("Please type /start first.", show_alert=True)
        return

    friends = await social_service.get_user_friends(user.id)
    limits = await subscription_service.get_plan_limits(user.id)
    max_friends = limits["max_friends"]

    buttons = []
    if not friends:
        text = (
            f"👥 <b>My Friends</b> (0 / {max_friends} slots used)\n\n"
            f"You don't have any friends yet.\n"
            f"When you and your chat partner both like each other, you become friends! 💙"
        )
        buttons.append([
            InlineKeyboardButton(text="🔍 Search ID", callback_data="conn:search"),
            InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub"),
        ])
    else:
        text = f"👥 <b>My Friends ({len(friends)} / {max_friends} slots used)</b>\n\n"
        for f in friends:
            text += f"• <b>{f['display_id']}</b> (Friends since {f['since']})\n"
            buttons.append([
                InlineKeyboardButton(
                    text=f"❌ Remove {f['display_id']}",
                    callback_data=f"friend:remove:{f['friend_user_id']}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub"),
        ])

    await send_or_edit(event, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("friend:remove:"))
async def handle_remove_friend_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    social_service: SocialService,
) -> None:
    """Removes a friend and updates view with back navigation."""
    if not callback.data or not callback.from_user:
        return

    friend_id = callback.data.split(":")[2]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return

    success, msg = await social_service.remove_friend(user.id, friend_id)
    await callback.answer(msg, show_alert=True)
    if callback.message and success:
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Back to Friends", callback_data="conn:friends")],
                [InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub")],
            ]
        )
        await safe_edit_text(callback.message, f"👥 {msg}", reply_markup=back_kb)


@router.message(F.text == "📬 Requests")
@router.message(Command("requests"))
@router.callback_query(F.data == "conn:requests")
async def show_requests(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    discovery_service: DiscoveryService,
) -> None:
    """Lists incoming connection requests with Accept/Decline actions."""
    user_tg = event.from_user
    if not user_tg:
        return

    user = await user_repo.get_by_telegram_id(user_tg.id)
    if not user:
        if isinstance(event, Message):
            await event.answer("Please type /start first.")
        else:
            await event.answer("Please type /start first.", show_alert=True)
        return

    reqs = await discovery_service.get_incoming_requests(user.id)
    buttons = []
    if not reqs:
        text = "📬 <b>Connection Requests</b>\n\nNo pending connection requests."
        buttons.append([InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub")])
    else:
        text = f"📬 <b>Pending Requests ({len(reqs)})</b>\n\n"
        for r in reqs:
            text += f"• <b>{r['sender_display_id']}</b> sent an invite ({r['created_at']})\n"
            buttons.append([
                InlineKeyboardButton(text=f"✅ Accept ({r['sender_display_id']})", callback_data=f"req:accept:{r['request_id']}"),
                InlineKeyboardButton(text="❌ Decline", callback_data=f"req:reject:{r['request_id']}"),
            ])
        buttons.append([InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub")])

    await send_or_edit(event, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("req:accept:"))
async def handle_accept_request_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    discovery_service: DiscoveryService,
) -> None:
    """Accepts an incoming connection request."""
    if not callback.data or not callback.from_user:
        return

    request_id = callback.data.split(":")[2]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return

    success, msg, _ = await discovery_service.accept_connection_request(request_id, user.id)
    await callback.answer(msg, show_alert=True)
    if callback.message:
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Back to Requests", callback_data="conn:requests")],
                [InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub")],
            ]
        )
        await safe_edit_text(callback.message, f"📬 {msg}", reply_markup=back_kb)


@router.callback_query(F.data.startswith("req:reject:"))
async def handle_reject_request_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    discovery_service: DiscoveryService,
) -> None:
    """Rejects an incoming connection request."""
    if not callback.data or not callback.from_user:
        return

    request_id = callback.data.split(":")[2]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return

    success, msg = await discovery_service.reject_connection_request(request_id, user.id)
    await callback.answer(msg, show_alert=True)
    if callback.message:
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Back to Requests", callback_data="conn:requests")],
                [InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub")],
            ]
        )
        await safe_edit_text(callback.message, f"📬 {msg}", reply_markup=back_kb)


@router.message(F.text == "💙 Who Liked Me")
@router.message(Command("likes"))
@router.callback_query(F.data == "conn:likes")
async def show_who_liked_me(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    social_service: SocialService,
) -> None:
    """Lists users who liked this profile with Like Back actions."""
    user_tg = event.from_user
    if not user_tg:
        return

    user = await user_repo.get_by_telegram_id(user_tg.id)
    if not user:
        if isinstance(event, Message):
            await event.answer("Please type /start first.")
        else:
            await event.answer("Please type /start first.", show_alert=True)
        return

    likes = await social_service.get_who_liked_me(user.id)
    buttons = []
    if not likes:
        text = (
            "💙 <b>Who Liked You</b>\n\n"
            "You have no pending likes at the moment.\n"
            "Keep chatting and express interest to discover mutual matches!"
        )
        buttons.append([InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub")])
    else:
        text = f"💙 <b>Who Liked You ({len(likes)} Pending)</b>\n\n"
        for lk in likes:
            text += f"• <b>{lk['sender_display_id']}</b> expressed interest!\n"
            buttons.append([
                InlineKeyboardButton(
                    text=f"💙 Like Back ({lk['sender_display_id']})",
                    callback_data=f"like_back:{lk['sender_id']}",
                )
            ])
        buttons.append([InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub")])

    await send_or_edit(event, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("like_back:"))
async def handle_like_back_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    social_service: SocialService,
) -> None:
    """Responds with reciprocal like."""
    if not callback.data or not callback.from_user:
        return

    target_id = callback.data.split(":")[1]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("User profile not found.", show_alert=True)
        return

    success, msg, _ = await social_service.express_like(
        sender_id=user.id,
        target_id=target_id,
    )
    await callback.answer(msg, show_alert=True)
    if callback.message:
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Back to Likes", callback_data="conn:likes")],
                [InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub")],
            ]
        )
        await safe_edit_text(callback.message, f"💙 <b>Response Sent:</b> {msg}", reply_markup=back_kb)


@router.message(F.text == "🔍 Search ID")
@router.message(Command("search"))
@router.callback_query(F.data == "conn:search")
async def start_search_id(
    event: Message | CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    subscription_service: SubscriptionService,
) -> None:
    """Initiates handle/ID lookup state."""
    user_tg = event.from_user
    if not user_tg:
        return

    user = await user_repo.get_by_telegram_id(user_tg.id)
    if not user:
        if isinstance(event, Message):
            await event.answer("Please type /start first.")
        else:
            await event.answer("Please type /start first.", show_alert=True)
        return

    limits = await subscription_service.get_plan_limits(user.id)
    daily_limit = limits["daily_searches_limit"]

    await state.set_state(SearchStates.waiting_for_query)
    text = (
        f"🔍 <b>Search User by ID or Handle</b>\n\n"
        f"Enter a permanent handle (e.g. <code>@unique_handle</code>) or LikBy ID:\n"
        f"<i>(Daily search quota: {daily_limit} searches per day)</i>\n\n"
        f"Send the handle now, or tap below to cancel."
    )
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Cancel & Return to Connections", callback_data="conn:hub")]
        ]
    )
    await send_or_edit(event, text, reply_markup=cancel_kb)


@router.message(SearchStates.waiting_for_query)
async def process_search_query(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    discovery_service: DiscoveryService,
) -> None:
    """Processes search query and returns preview card."""
    query = (message.text or "").strip()
    if query == "/cancel":
        await state.clear()
        cancel_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Return to Connections", callback_data="conn:hub")]
            ]
        )
        await message.answer("Search cancelled.", reply_markup=cancel_kb)
        return

    if not message.from_user:
        return

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        return

    success, msg, preview = await discovery_service.search_user(
        requester_id=user.id,
        query=query,
    )
    await state.clear()

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub")]
        ]
    )

    if not success or not preview:
        await message.answer(f"❌ {msg}", reply_markup=back_kb)
        return

    friend_status = "Yes (Friends 💙)" if preview["is_friend"] else "Not Friends"

    buttons = []
    if not preview["is_friend"]:
        if preview["has_pending_request"]:
            buttons.append([InlineKeyboardButton(text="⏳ Request Pending", callback_data="req:noop")])
        else:
            buttons.append([
                InlineKeyboardButton(
                    text="📬 Send Connection Request",
                    callback_data=f"connect:send:{preview['user_id']}",
                )
            ])
    buttons.append([InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub")])

    await message.answer(
        f"🔍 <b>User Found</b>\n\n"
        f"• <b>Handle:</b> {preview['display_id']}\n"
        f"• <b>Activity:</b> {preview['presence']}\n"
        f"• <b>Friendship:</b> {friend_status}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("connect:send:"))
async def handle_send_connection_request(
    callback: CallbackQuery,
    user_repo: UserRepository,
    discovery_service: DiscoveryService,
) -> None:
    """Sends connection request from search result."""
    if not callback.data or not callback.from_user:
        return

    target_id = callback.data.split(":")[2]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return

    success, msg, _ = await discovery_service.send_connection_request(
        sender_id=user.id,
        target_id=target_id,
    )
    await callback.answer(msg, show_alert=True)
    if callback.message:
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub")]
            ]
        )
        await safe_edit_text(callback.message, f"📬 {msg}", reply_markup=back_kb)


# ==============================================================================
# 5. 💬 My Chats Hub
# ==============================================================================

@router.message(F.text.in_(["💬 My Chats", "💬 Chats"]))
@router.message(Command("chats"))
@router.callback_query(F.data == "chat:hub")
async def show_my_chats(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    session_repo: ChatSessionRepository,
) -> None:
    """Conversations Hub: Inspects active session or offers matchmaking CTA."""
    user_tg = event.from_user
    if not user_tg:
        return

    user = await user_repo.get_by_telegram_id(user_tg.id)
    if not user:
        if isinstance(event, Message):
            await event.answer("Please type /start first.")
        else:
            await event.answer("Please type /start first.", show_alert=True)
        return

    active_session = await session_repo.get_active_by_user_id(user.id)
    if active_session:
        text = (
            f"💬 <b>Active Chat Session</b>\n\n"
            f"• <b>Session ID:</b> <code>{active_session.id}</code>\n"
            f"• <b>Status:</b> 🟢 Live & Connected\n"
            f"• <b>Partner:</b> Anonymous Partner\n\n"
            f"Type and send any message directly to chat with your partner.\n"
            f"Use the interactive controls below to play, skip, or end:"
        )
        kb = get_chat_hub_keyboard(is_active=True, session_id=active_session.id)
    else:
        text = (
            "💬 <b>Chat Sessions</b>\n\n"
            "You have no active chat session right now.\n"
            "Tap <b>🎲 Find Match</b> below to connect with an anonymous partner!"
        )
        kb = get_chat_hub_keyboard(is_active=False)

    await send_or_edit(event, text, reply_markup=kb)
