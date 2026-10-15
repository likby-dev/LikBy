"""
likby.telegram.handlers.report
Handlers for abuse reporting, bilateral blocking, and safety mitigation.
"""

import uuid
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from likby.domain.entities.block import UserBlock
from likby.domain.entities.report import Report
from likby.domain.enums import ReportCategory, TerminationReason, UserState
from likby.repositories.interfaces import (
    BlockRepository,
    ReportRepository,
    UserRepository,
)
from likby.services.chat_relay_service import ChatRelayService
from likby.telegram.keyboards import get_main_menu_keyboard
from likby.telegram.utils import safe_edit_text

router = Router(name="report")


def get_report_categories_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for selecting abuse reason."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔞 Explicit / NSFW Content", callback_data="report_cat:NSFW")],
            [InlineKeyboardButton(text="🦹 Harassment / Hate Speech", callback_data="report_cat:HARASSMENT")],
            [InlineKeyboardButton(text="🤖 Spam / Commercial Ad", callback_data="report_cat:SPAM")],
            [InlineKeyboardButton(text="👶 Underage User", callback_data="report_cat:UNDERAGE")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="report_cat:cancel")],
        ]
    )


@router.message(F.text == "⚠️ Report")
@router.message(Command("report"))
async def prompt_report(message: Message, chat_relay: ChatRelayService) -> None:
    if not message.from_user:
        return

    tg_id = message.from_user.id
    cached = await chat_relay.get_or_warm_session(tg_id)
    if not cached:
        await message.answer("You can only file a report during an active chat session.")
        return

    await message.answer(
        "⚠️ <b>Report User & End Chat</b>\n\n"
        "Reporting immediately ends the chat and adds this person to your permanent blocklist so you never match again.\n\n"
        "Please select a reason:",
        parse_mode="HTML",
        reply_markup=get_report_categories_keyboard(),
    )


@router.callback_query(F.data.startswith("report_cat:"))
async def process_report(
    callback: CallbackQuery,
    user_repo: UserRepository,
    block_repo: BlockRepository,
    report_repo: ReportRepository,
    chat_relay: ChatRelayService,
) -> None:
    if not callback.data or not callback.from_user or not callback.message:
        return

    cat_str = callback.data.split(":")[1]
    if cat_str == "cancel":
        await callback.answer("Report cancelled.")
        await callback.message.delete()
        return

    await callback.answer("Report submitted.", show_alert=True)
    tg_id = callback.from_user.id
    cached = await chat_relay.get_or_warm_session(tg_id)
    if not cached:
        await safe_edit_text(callback.message, "Session already closed.")
        return

    reporter_id = cached.user_a_id if tg_id == cached.user_a_tg_id else cached.user_b_id
    reported_id = cached.get_partner_user_id(reporter_id)

    # 1. Save Report
    report = Report(
        id=f"rep_{uuid.uuid4().hex[:12]}",
        reporter_id=reporter_id,
        reported_id=reported_id,
        session_id=cached.session_id,
        category=ReportCategory(cat_str),
        reason=f"User reported with category: {cat_str}",
    )
    await report_repo.save(report)

    # 2. Save Bilateral Block
    block = UserBlock(
        id=f"blk_{uuid.uuid4().hex[:12]}",
        blocker_id=reporter_id,
        blocked_id=reported_id,
    )
    await block_repo.save(block)

    # 3. Apply penalty to reported user
    reported_user = await user_repo.get_by_id(reported_id)
    if reported_user:
        reported_user.apply_report_penalty()
        await user_repo.save(reported_user)

    # 4. Terminate chat session
    await chat_relay.end_active_session(
        sender_tg_id=tg_id,
        reason=TerminationReason.USER_REPORTED,
    )

    # 5. Restore reporter user state
    reporter_user = await user_repo.get_by_id(reporter_id)
    if reporter_user:
        reporter_user.transition_state(UserState.MAIN_MENU)
        await user_repo.save(reporter_user)

    await callback.message.delete()
    await callback.message.answer(
        "🛡️ <b>Thank you. Your report has been recorded.</b>\n\n"
        "The conversation has been terminated and this user has been blocked.\n"
        "Returned to Main Menu.",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )
