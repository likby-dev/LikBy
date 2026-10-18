"""
likby.telegram.handlers.menu
Authoritative handlers for LikBy Navigation Hubs:
- 👤 Profile & VIP Hub (Profile, Karma, Settings, VIP Plans, Safety)
- 👥 Connections Hub (Friends, Requests, Who Liked Me, ID Search, Referrals)
- 💬 My Chats Hub (Active conversation controls, instant matchmaking, transcripts)
"""

from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
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
    get_chat_hub_keyboard,
    get_connections_hub_keyboard,
    get_main_menu_keyboard,
    get_profile_vip_keyboard,
)
from likby.telegram.states import EditProfileStates, SearchStates
from likby.telegram.utils import safe_edit_text

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
    interests_str = ", ".join(profile.interests).title() if profile.interests else "None selected"
    gender_str = profile.gender.value.replace("_", " ").title()

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
        f"• <b>Age & Gender:</b> {profile.age} • {gender_str}\n"
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
            [InlineKeyboardButton(text="« Back to Profile Hub", callback_data="vip:hub")]
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
