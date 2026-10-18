"""
likby.telegram.handlers.payments
Telegram bot payment, subscription, and referral handlers.
Adheres strictly to Telegram Stars (XTR) for in-bot digital goods checkout.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from likby.domain.entities.subscription import PLAN_SPECS, SubscriptionTier
from likby.domain.enums import FeatureKey, PaymentProviderType
from likby.repositories.interfaces import ProfileRepository, UserRepository
from likby.services.payment_service import PaymentService
from likby.services.referral_service import ReferralService
from likby.services.subscription_service import SubscriptionService
from likby.services.usage_service import UsageService
from likby.telegram.keyboards import (
    get_main_menu_keyboard,
    get_plan_card_keyboard,
    get_referral_keyboard,
    get_subscription_keyboard,
)

router = Router(name="payments")


# --- 1. /plans & 💎 Subscription Menu ---

@router.message(Command("plans"))
@router.message(Command("subscription"))
@router.message(Command("vip"))
@router.message(F.text == "💎 Subscription")
@router.callback_query(F.data == "sub:plans")
async def show_plans_command(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    subscription_service: SubscriptionService,
) -> None:
    user_tg_id = event.from_user.id if event.from_user else 0
    user = await user_repo.get_by_telegram_id(user_tg_id)
    if not user:
        if isinstance(event, Message):
            await event.answer("Please type /start first.")
        else:
            await event.answer("Please type /start first.", show_alert=True)
        return

    ent = await subscription_service.get_or_create_entitlement(user.id)
    active_tier_name = PLAN_SPECS.get(ent.tier, {}).get("display_name", ent.tier.value)

    text = (
        f"💎 <b>LikBy Subscription Plans</b>\n\n"
        f"Your Current Active Plan: <b>{active_tier_name}</b>\n\n"
        f"<b>1. LikBy Base — Free Forever</b>\n"
        f"• Price: <b>₹0 / Free</b>\n"
        f"• Duration: <b>No expiry</b>\n"
        f"• Max Friends: <b>3</b>\n"
        f"• Likes: <b>25 / day</b> | ID Searches: <b>10 / day</b>\n"
        f"• Direct Requests: <b>3 / day</b> | Games: <b>3 / day</b>\n\n"
        f"<b>2. LikBy Spark — 24-Hour Pass</b> ⚡\n"
        f"• Price: <b>15 ⭐️ (Telegram Stars)</b> / ₹19\n"
        f"• Duration: <b>24 hours</b>\n"
        f"• Max Friends: <b>5</b>\n"
        f"• Likes: <b>50 / day</b> | ID Searches: <b>25 / day</b>\n"
        f"• Direct Requests: <b>5 / day</b> | Games: <b>10 / day</b>\n"
        f"• <b>+1 Profile Match Boost</b>\n"
        f"<i>💡 Can also be earned for free via /invite!</i>\n\n"
        f"<b>3. LikBy Premium — 30 Days</b> 🌟\n"
        f"• Price: <b>60 ⭐️ (Telegram Stars)</b> / ₹79\n"
        f"• Duration: <b>30 days</b> (Optional 90d: 150 ⭐️ / ₹199)\n"
        f"• Max Friends: <b>15</b>\n"
        f"• Likes: <b>100 / day</b> | ID Searches: <b>100 / day</b>\n"
        f"• Direct Requests: <b>15 / day</b> | Games: <b>25 / day</b>\n"
        f"• <b>+2 Profile Match Boosts</b>\n\n"
        f"<b>4. LikBy Diamond — VIP Access</b> 👑\n"
        f"• Price: <b>120 ⭐️ (Telegram Stars)</b> / ₹149\n"
        f"• Duration: <b>30 days</b> (Optional 90d: 300 ⭐️ / ₹399)\n"
        f"• Max Friends: <b>50</b>\n"
        f"• Likes: <b>200 / day</b> | ID Searches: <b>250 / day</b>\n"
        f"• Direct Requests: <b>30 / day</b> | Games: <b>50 / day</b>\n"
        f"• <b>+4 Profile Match Boosts & Priority Support</b>\n\n"
        f"<i>Note: In-bot checkouts use official Telegram Stars (⭐️). Existing friends and chat history survive downgrades.</i>"
    )

    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML", reply_markup=get_subscription_keyboard())
    else:
        await event.answer()
        if event.message:
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=get_subscription_keyboard())


# --- 2. /myplan ---

@router.message(Command("myplan"))
@router.callback_query(F.data == "sub:myplan")
async def show_my_plan(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    subscription_service: SubscriptionService,
    usage_service: UsageService,
) -> None:
    user_tg_id = event.from_user.id if event.from_user else 0
    user = await user_repo.get_by_telegram_id(user_tg_id)
    if not user:
        return

    limits = await subscription_service.get_plan_limits(user.id)
    summary = await usage_service.get_user_daily_summary(user.id)

    # Expiry formatting
    expiry_text = "Never (Lifetime)"
    if limits.get("expires_at"):
        try:
            dt = datetime.fromisoformat(limits["expires_at"])
            # Format in Asia/Kolkata
            dt_kolkata = dt.astimezone(ZoneInfo("Asia/Kolkata"))
            expiry_text = dt_kolkata.strftime("%d %b %Y, %I:%M %p IST")
        except Exception:
            expiry_text = limits["expires_at"]

    text = (
        f"📊 <b>My Subscription & Daily Quotas</b>\n\n"
        f"Current Plan: <b>{limits['display_name']}</b>\n"
        f"Expires: <b>{expiry_text}</b>\n"
        f"Friend Capacity: <b>{limits['max_friends']} Max</b>\n"
        f"Available Match Boosts: <b>{limits['profile_boosts']}</b>\n\n"
        f"<b>Today's Daily Consumption:</b>\n"
        f"• Likes: <b>{summary['LIKES']['used']} / {summary['LIKES']['limit']}</b> ({summary['LIKES']['remaining']} left)\n"
        f"• ID Lookups: <b>{summary['SEARCHES']['used']} / {summary['SEARCHES']['limit']}</b> ({summary['SEARCHES']['remaining']} left)\n"
        f"• Direct Requests: <b>{summary['REQUESTS']['used']} / {summary['REQUESTS']['limit']}</b> ({summary['REQUESTS']['remaining']} left)\n"
        f"• Games Started: <b>{summary['GAMES']['used']} / {summary['GAMES']['limit']}</b> ({summary['GAMES']['remaining']} left)\n"
        f"• Media Uploads: <b>{summary.get('UPLOADS', {}).get('used', 0)} / {limits.get('daily_uploads_limit', 20)}</b> ({summary.get('UPLOADS', {}).get('remaining', limits.get('daily_uploads_limit', 20))} left)\n"
        f"• Media Received: <b>{summary.get('RECEIVED', {}).get('used', 0)} / {limits.get('daily_receive_limit', 10)}</b> ({summary.get('RECEIVED', {}).get('remaining', limits.get('daily_receive_limit', 10))} left)\n\n"
        f"🛡 <i>Media protected with Telegram Content Protection. Media resets at 00:00 UTC.</i>"
    )

    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML", reply_markup=get_subscription_keyboard())
    else:
        await event.answer()
        if event.message:
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=get_subscription_keyboard())


# --- 3. /upgrade & Telegram Stars Purchase Initiation ---

@router.message(Command("upgrade"))
async def show_upgrade_command(message: Message) -> None:
    await message.answer(
        "⚡ <b>Upgrade Your LikBy Experience</b>\n\n"
        "Select a subscription tier below to purchase instantly with Telegram Stars (⭐️):",
        parse_mode="HTML",
        reply_markup=get_subscription_keyboard(),
    )


@router.callback_query(F.data.startswith("sub:buy:"))
async def handle_buy_plan_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    payment_service: PaymentService,
) -> None:
    if not callback.data or not callback.from_user:
        return

    plan_code = callback.data.split(":")[2].upper()
    try:
        tier = SubscriptionTier(plan_code)
    except ValueError:
        await callback.answer("Invalid plan.", show_alert=True)
        return

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Please type /start first.", show_alert=True)
        return

    spec = PLAN_SPECS[tier]
    stars_amount = spec["stars_amount"]

    # 1. Create order on server
    success, msg, order, checkout_data = await payment_service.create_checkout_order(
        user_id=user.id,
        plan_code=plan_code,
        provider=PaymentProviderType.TELEGRAM_STARS,
    )

    if not success or not order:
        await callback.answer(f"Error: {msg}", show_alert=True)
        return

    await callback.answer()

    # 2. Issue Telegram Stars invoice
    prices = [LabeledPrice(label=spec["display_name"], amount=stars_amount)]

    if callback.message:
        await callback.message.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"{spec['display_name']}",
            description=spec["description"],
            payload=order.internal_order_id,
            currency="XTR",
            prices=prices,
        )


# --- 4. Pre-Checkout Query Verification ---

@router.pre_checkout_query()
async def process_pre_checkout_query(
    pre_checkout_query: PreCheckoutQuery,
    payment_service: PaymentService,
) -> None:
    """
    Mandatory Telegram Stars pre-checkout validation.
    Must respond within 10 seconds.
    """
    payload = pre_checkout_query.invoice_payload
    currency = pre_checkout_query.currency
    total_amount = pre_checkout_query.total_amount

    # Look up order
    order = await payment_service._order_repo.get_by_internal_order_id(payload)
    if not order:
        await pre_checkout_query.answer(ok=False, error_message="Order not found or expired.")
        return

    if currency != "XTR" or total_amount != order.amount_minor_units:
        await pre_checkout_query.answer(ok=False, error_message="Amount or currency mismatch.")
        return

    # Approve checkout
    await pre_checkout_query.answer(ok=True)


# --- 5. Successful Payment Confirmation ---

@router.message(F.successful_payment)
async def process_successful_payment(
    message: Message,
    user_repo: UserRepository,
    payment_service: PaymentService,
) -> None:
    if not message.successful_payment or not message.from_user:
        return

    sp = message.successful_payment
    internal_order_id = sp.invoice_payload
    charge_id = sp.telegram_payment_charge_id
    provider_charge_id = sp.provider_payment_charge_id
    total_amount = sp.total_amount

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        return

    success, msg, txn = await payment_service.settle_telegram_stars_payment(
        user_id=user.id,
        internal_order_id=internal_order_id,
        telegram_payment_charge_id=charge_id,
        provider_payment_charge_id=provider_charge_id,
        total_amount=total_amount,
    )

    if success:
        await message.answer(
            f"🎉 <b>Payment Successful!</b>\n\n"
            f"Your subscription has been activated immediately.\n"
            f"• Charge ID: <code>{charge_id}</code>\n"
            f"• Amount Paid: <b>{total_amount} ⭐️</b>\n\n"
            f"Type /myplan to view your updated quotas and feature limits. Thank you for supporting LikBy! 💙",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
    else:
        await message.answer(
            f"⚠️ Payment confirmed by Telegram, but error settling order: {msg}\n"
            f"Please contact support via /paysupport with charge ID <code>{charge_id}</code>.",
            parse_mode="HTML",
        )


# --- 6. /invite & Referral-Based Spark Rewards ---

@router.message(Command("invite"))
@router.callback_query(F.data == "sub:invite")
async def show_referral_command(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    referral_service: ReferralService,
) -> None:
    user_tg_id = event.from_user.id if event.from_user else 0
    user = await user_repo.get_by_telegram_id(user_tg_id)
    if not user:
        return

    unique_id = user.unique_id or f"u{user.telegram_id}"
    invite_link = referral_service.generate_referral_link(unique_id)
    stats = await referral_service.get_referrer_stats(user.id)

    text = (
        f"🎁 <b>Invite Friends — Earn Free LikBy Spark Passes!</b>\n\n"
        f"Share your unique link with friends:\n"
        f"👉 <code>{invite_link}</code>\n\n"
        f"<b>How it works:</b>\n"
        f"1. Your friend joins LikBy using your link.\n"
        f"2. When they complete profile setup & 18+ verification, you instantly receive a <b>Free 24-Hour LikBy Spark Pass</b> (⚡)!\n"
        f"3. No purchase required for either of you.\n\n"
        f"<b>Your Referral Stats:</b>\n"
        f"• Total Invited: <b>{stats['total_invites']}</b>\n"
        f"• Qualified & Rewarded: <b>{stats['qualified_invites']}</b>\n"
        f"• Rewarded in last 30 days: <b>{stats['recent_rewards_30d']} / {stats['max_rewards_30d']} Max</b>\n"
        f"• Available Reward Slots: <b>{stats['remaining_reward_slots']}</b>"
    )

    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML", reply_markup=get_referral_keyboard())
    else:
        await event.answer()
        if event.message:
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=get_referral_keyboard())


# --- 7. /payment_history ---

@router.message(Command("payment_history"))
@router.callback_query(F.data == "sub:history")
async def show_payment_history(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    payment_service: PaymentService,
) -> None:
    user_tg_id = event.from_user.id if event.from_user else 0
    user = await user_repo.get_by_telegram_id(user_tg_id)
    if not user:
        return

    history = await payment_service.get_user_transaction_history(user.id)
    if not history:
        msg_text = (
            "🧾 <b>Payment History</b>\n\n"
            "You have no past transactions on record.\n"
            "All free Base features remain available to you at all times."
        )
    else:
        lines = ["🧾 <b>Your Payment History</b>\n"]
        for item in history[:10]:
            lines.append(
                f"• <b>{item['plan_display_name']}</b> — {item['amount']} ({item['provider']})\n"
                f"  Status: <code>{item['status']}</code> | Date: {item['created_at']}\n"
                f"  Ref: <code>{item['internal_order_id']}</code>\n"
            )
        msg_text = "\n".join(lines)

    if isinstance(event, Message):
        await event.answer(msg_text, parse_mode="HTML", reply_markup=get_subscription_keyboard())
    else:
        await event.answer()
        if event.message:
            await event.message.edit_text(msg_text, parse_mode="HTML", reply_markup=get_subscription_keyboard())


# --- 8. /terms & /privacy & /paysupport ---

@router.message(Command("terms"))
@router.callback_query(F.data == "sub:terms")
async def show_subscription_terms(event: Message | CallbackQuery) -> None:
    text = (
        "📜 <b>LikBy Subscription Terms & Refund Policy</b>\n\n"
        "<b>1. Digital Entitlements:</b>\n"
        "LikBy subscriptions (Spark, Premium, Diamond) unlock enhanced digital discovery quotas, friend capacity, and games. "
        "LikBy Base remains 100% free forever.\n\n"
        "<b>2. Non-Recurring / One-Time Passes:</b>\n"
        "Subscriptions do not automatically renew without your explicit action. Once expired, your account seamlessly transitions back to Base limits.\n\n"
        "<b>3. Friend & Chat Preservation:</b>\n"
        "Downgrades never delete your existing friends or chat history. Existing accepted relationships remain accessible.\n\n"
        "<b>4. Refund Policy:</b>\n"
        "In accordance with Telegram Stars guidelines, digital goods consumed immediately upon purchase are generally non-refundable. "
        "If you experience a technical failure or double charge, contact /paysupport within 48 hours for review and refund processing."
    )
    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML", reply_markup=get_subscription_keyboard())
    else:
        await event.answer()
        if event.message:
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=get_subscription_keyboard())


@router.message(Command("privacy"))
async def show_privacy_policy(message: Message) -> None:
    await message.answer(
        "🛡 <b>LikBy Privacy & Security Guarantee</b>\n\n"
        "• <b>No Financial Credentials Stored:</b> LikBy never stores, sees, or processes credit card numbers, CVVs, or bank logins. "
        "Payments are handled securely by Telegram Stars or Razorpay.\n"
        "• <b>Zero Message Text Logging:</b> Chat messages are relayed in-flight and purged from RAM once delivered.\n"
        "• <b>Anonymity:</b> Your Telegram handle and phone number are never shared with partners without explicit mutual consent.",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )


@router.message(Command("paysupport"))
@router.callback_query(F.data == "sub:paysupport")
async def show_payment_support(event: Message | CallbackQuery) -> None:
    text = (
        "💬 <b>LikBy Payment Support</b>\n\n"
        "Having issues with a Telegram Stars or web purchase?\n\n"
        "<b>Before contacting support, please prepare:</b>\n"
        "1. Your Telegram User ID\n"
        "2. The Order Reference (e.g. <code>LIKBY-TEL-...</code>)\n"
        "3. Telegram Stars Charge ID from your Telegram receipt\n\n"
        "Contact our billing desk: <b>support@likby.com</b> or message <b>@LikBy_bot</b>."
    )
    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML", reply_markup=get_subscription_keyboard())
    else:
        await event.answer()
        if event.message:
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=get_subscription_keyboard())
