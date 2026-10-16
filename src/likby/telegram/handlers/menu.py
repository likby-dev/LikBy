"""
likby.telegram.handlers.menu
Handlers for Main Menu options: Profile, Karma, Who Liked Me, Friends, Search ID, Requests, Subscription, and Safety.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from likby.domain.enums import SubscriptionTier
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
    get_main_menu_keyboard,
    get_subscription_keyboard,
)
from likby.telegram.states import EditProfileStates, SearchStates

router = Router(name="menu")


# --- 1. My Profile ---

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
        f"• <b>Karma Score:</b> {user.karma_score} 🌟\n\n"
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


# --- 2. My Karma ---

@router.message(F.text == "🌟 My Karma")
@router.message(Command("karma"))
async def show_karma(
    message: Message,
    user_repo: UserRepository,
    karma_service: KarmaService,
) -> None:
    if not message.from_user:
        return

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Please type /start first.")
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

    await message.answer(
        f"🌟 <b>Your LikBy Karma & Reputation</b>\n\n"
        f"Current Karma Score: <b>{score}</b> / 500\n\n"
        f"<b>How Karma Works:</b>\n"
        f"• Good chat rating: <b>+1</b>\n"
        f"• Disliked chat rating: <b>-1</b>\n"
        f"• Respectful chatting builds higher matchmaking priority!"
        f"{history_text}",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )


# --- 3. Who Liked Me ---

@router.message(F.text == "💙 Who Liked Me")
@router.message(Command("likes"))
async def show_who_liked_me(
    message: Message,
    user_repo: UserRepository,
    social_service: SocialService,
) -> None:
    if not message.from_user:
        return

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Please type /start first.")
        return

    likes = await social_service.get_who_liked_me(user.id)
    if not likes:
        await message.answer(
            "💙 <b>Who Liked You</b>\n\n"
            "You have no pending likes at the moment.\n"
            "Keep chatting and express interest to discover mutual matches!",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    text = f"💙 <b>Who Liked You ({len(likes)} Pending)</b>\n\n"
    buttons = []
    for lk in likes:
        text += f"• <b>{lk['sender_display_id']}</b> expressed interest!\n"
        buttons.append([
            InlineKeyboardButton(
                text=f"💙 Like Back ({lk['sender_display_id']})",
                callback_data=f"like_back:{lk['sender_id']}",
            )
        ])

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("like_back:"))
async def handle_like_back_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    social_service: SocialService,
) -> None:
    if not callback.data or not callback.from_user:
        return

    target_id = callback.data.split(":")[1]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("User profile not found.")
        return

    success, msg, friendship = await social_service.express_like(
        sender_id=user.id,
        target_id=target_id,
    )
    await callback.answer(msg, show_alert=True)
    if callback.message:
        await callback.message.edit_text(
            f"💙 <b>Response Sent:</b> {msg}",
            parse_mode="HTML",
        )


# --- 4. My Friends ---

@router.message(F.text == "👥 My Friends")
@router.message(Command("friends"))
async def show_friends(
    message: Message,
    user_repo: UserRepository,
    social_service: SocialService,
    subscription_service: SubscriptionService,
) -> None:
    if not message.from_user:
        return

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Please type /start first.")
        return

    friends = await social_service.get_user_friends(user.id)
    limits = await subscription_service.get_plan_limits(user.id)
    max_friends = limits["max_friends"]

    if not friends:
        await message.answer(
            f"👥 <b>My Friends</b> (0 / {max_friends} slots used)\n\n"
            f"You don't have any friends yet.\n"
            f"When you and your chat partner both like each other, you become friends! 💙",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    text = f"👥 <b>My Friends ({len(friends)} / {max_friends} slots used)</b>\n\n"
    buttons = []
    for f in friends:
        text += f"• <b>{f['display_id']}</b> (Friends since {f['since']})\n"
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ Remove {f['display_id']}",
                callback_data=f"friend:remove:{f['friend_user_id']}",
            )
        ])

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("friend:remove:"))
async def handle_remove_friend_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    social_service: SocialService,
) -> None:
    if not callback.data or not callback.from_user:
        return

    friend_id = callback.data.split(":")[2]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return

    success, msg = await social_service.remove_friend(user.id, friend_id)
    await callback.answer(msg, show_alert=True)
    if callback.message and success:
        await callback.message.edit_text(f"👥 {msg}")


# --- 5. Search ID & Connections ---

@router.message(F.text == "🔍 Search ID")
@router.message(Command("search"))
async def start_search_id(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    subscription_service: SubscriptionService,
) -> None:
    if not message.from_user:
        return

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Please type /start first.")
        return

    limits = await subscription_service.get_plan_limits(user.id)
    daily_limit = limits["daily_searches_limit"]

    await state.set_state(SearchStates.waiting_for_query)
    await message.answer(
        f"🔍 <b>Search User by ID or Handle</b>\n\n"
        f"Enter a permanent handle (e.g. <code>@unique_handle</code>) or LikBy ID:\n"
        f"<i>(Daily search quota: {daily_limit} searches per day)</i>\n\n"
        f"Send the handle or type /cancel to abort.",
        parse_mode="HTML",
    )


@router.message(SearchStates.waiting_for_query)
async def process_search_query(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    discovery_service: DiscoveryService,
) -> None:
    query = (message.text or "").strip()
    if query == "/cancel":
        await state.clear()
        await message.answer("Search cancelled.", reply_markup=get_main_menu_keyboard())
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

    if not success or not preview:
        await message.answer(f"❌ {msg}", reply_markup=get_main_menu_keyboard())
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

    await message.answer(
        f"🔍 <b>User Found</b>\n\n"
        f"• <b>Handle:</b> {preview['display_id']}\n"
        f"• <b>Activity:</b> {preview['presence']}\n"
        f"• <b>Friendship:</b> {friend_status}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None,
    )


@router.callback_query(F.data.startswith("connect:send:"))
async def handle_send_connection_request(
    callback: CallbackQuery,
    user_repo: UserRepository,
    discovery_service: DiscoveryService,
) -> None:
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
        await callback.message.edit_text(f"📬 {msg}")


# --- 6. Connection Requests ---

@router.message(F.text == "📬 Requests")
@router.message(Command("requests"))
async def show_requests(
    message: Message,
    user_repo: UserRepository,
    discovery_service: DiscoveryService,
) -> None:
    if not message.from_user:
        return

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Please type /start first.")
        return

    reqs = await discovery_service.get_incoming_requests(user.id)
    if not reqs:
        await message.answer(
            "📬 <b>Connection Requests</b>\n\nNo pending connection requests.",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    text = f"📬 <b>Pending Requests ({len(reqs)})</b>\n\n"
    buttons = []
    for r in reqs:
        text += f"• <b>{r['sender_display_id']}</b> sent you an invite ({r['created_at']})\n"
        buttons.append([
            InlineKeyboardButton(text=f"✅ Accept ({r['sender_display_id']})", callback_data=f"req:accept:{r['request_id']}"),
            InlineKeyboardButton(text=f"❌ Decline", callback_data=f"req:reject:{r['request_id']}"),
        ])

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("req:accept:"))
async def handle_accept_request_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    discovery_service: DiscoveryService,
) -> None:
    if not callback.data or not callback.from_user:
        return

    request_id = callback.data.split(":")[2]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return

    success, msg, _ = await discovery_service.accept_connection_request(request_id, user.id)
    await callback.answer(msg, show_alert=True)
    if callback.message:
        await callback.message.edit_text(f"📬 {msg}")


@router.callback_query(F.data.startswith("req:reject:"))
async def handle_reject_request_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    discovery_service: DiscoveryService,
) -> None:
    if not callback.data or not callback.from_user:
        return

    request_id = callback.data.split(":")[2]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return

    success, msg = await discovery_service.reject_connection_request(request_id, user.id)
    await callback.answer(msg, show_alert=True)
    if callback.message:
        await callback.message.edit_text(f"📬 {msg}")


# --- 7. Subscription & Entitlements ---

@router.message(F.text == "💎 Subscription")
@router.message(Command("subscription"))
async def show_subscription(
    message: Message,
    user_repo: UserRepository,
    subscription_service: SubscriptionService,
) -> None:
    if not message.from_user:
        return

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Please type /start first.")
        return

    limits = await subscription_service.get_plan_limits(user.id)
    tier = limits["tier"]
    max_friends = limits["max_friends"]
    daily_searches = limits["daily_searches_limit"]
    daily_requests = limits["daily_requests_limit"]

    await message.answer(
        f"💎 <b>LikBy Subscription & Entitlements</b>\n\n"
        f"Active Plan: <b>{tier.upper()}</b>\n\n"
        f"<b>Current Feature Limits:</b>\n"
        f"• Max Friends: <b>{max_friends}</b>\n"
        f"• Daily ID Searches: <b>{daily_searches} / day</b>\n"
        f"• Daily Connection Requests: <b>{daily_requests} / day</b>\n"
        f"• View Incoming Likes: <b>Included</b> 💙\n\n"
        f"Upgrade your tier to increase your limits:",
        parse_mode="HTML",
        reply_markup=get_subscription_keyboard(),
    )


@router.callback_query(F.data.startswith("sub:upgrade:"))
async def handle_upgrade_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    subscription_service: SubscriptionService,
) -> None:
    if not callback.data or not callback.from_user:
        return

    tier_str = callback.data.split(":")[2]
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return

    new_tier = SubscriptionTier(tier_str)
    ent = await subscription_service.upgrade_tier(user.id, new_tier, duration_days=30)
    await callback.answer(f"Upgraded to {new_tier.value.upper()}!", show_alert=True)

    if callback.message:
        await callback.message.edit_text(
            f"🎉 <b>Subscription Upgraded to {new_tier.value.upper()}!</b>\n\n"
            f"• Max Friends: <b>{ent.max_friends}</b>\n"
            f"• Daily ID Searches: <b>{ent.daily_searches_limit}</b>\n"
            f"• Daily Requests: <b>{ent.daily_requests_limit}</b>\n\n"
            f"Valid for 30 days. Thank you for supporting LikBy! 💙",
            parse_mode="HTML",
        )


@router.callback_query(F.data == "sub:status")
async def handle_sub_status_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    subscription_service: SubscriptionService,
) -> None:
    if not callback.from_user:
        return

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        return

    limits = await subscription_service.get_plan_limits(user.id)
    await callback.answer(f"Active Plan: {limits['tier'].upper()}", show_alert=True)


# --- 8. My Chats ---

@router.message(F.text == "💬 My Chats")
@router.message(Command("chats"))
async def show_my_chats(
    message: Message,
    user_repo: UserRepository,
    session_repo: ChatSessionRepository,
) -> None:
    if not message.from_user:
        return

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Please type /start first.")
        return

    active_session = await session_repo.get_active_by_user_id(user.id)
    if active_session:
        await message.answer(
            f"💬 <b>Active Chat Session:</b> <code>{active_session.id}</code>\n"
            f"You are currently chatting with an anonymous partner.\n"
            f"Send messages in chat or tap <b>🚫 End Chat</b> to finish.",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "💬 <b>Chat Sessions</b>\n\n"
            "You have no active chat session right now.\n"
            "Tap <b>🎲 Find Someone</b> to start a new anonymous chat!",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )


# --- 9. Help & Guidelines ---

@router.message(F.text == "🛡 Help & Safety")
@router.message(F.text == "📜 Guidelines")
@router.message(Command("guidelines"))
@router.message(Command("help"))
async def show_help_and_safety(message: Message) -> None:
    await message.answer(
        "🛡️ <b>LikBy Safety & Guidelines</b>\n\n"
        "LikBy is built on privacy, mutual respect, and safe discovery.\n\n"
        "<b>Core Principles:</b>\n"
        "1. <b>Strict Anonymity:</b> Your Telegram account, phone number, and location are never revealed.\n"
        "2. <b>Zero Tolerance:</b> Harassment, hate speech, explicit content, and spam result in immediate suspension.\n"
        "3. <b>Adults Only (18+):</b> Users must be 18 or older.\n"
        "4. <b>Safety Controls:</b> You can tap <b>⚠️ Report</b> during any chat to instantly disconnect and permanently block a partner.\n\n"
        "<b>Need help?</b> Contact LikBy Support or ping @LikBy_bot.",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )
