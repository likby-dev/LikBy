"""
likby.telegram.handlers.play
Telegram Bot interface and entry points for LikBy Play gaming ecosystem.
Handles /play, /games, /duels, /solo, /mygames commands and interactive game menus.
"""

from typing import Optional
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from likby.config import get_settings
from likby.domain.entities.play_game import GAME_CATALOGUE
from likby.domain.enums import GameMode, SubscriptionTier
from likby.repositories.interfaces import UserRepository
from likby.services.gaming_entitlement_service import GamingEntitlementService
from likby.services.play_game_service import PlayGameService
from likby.telegram.keyboards import get_play_hub_keyboard

router = Router(name="play")


WELCOME_TEXT = (
    "<b>Welcome to LikBy Play</b> 🩵\n\n"
    "<i>Every connection has a game. Every game creates a moment.</i>\n\n"
    "Challenge someone you've connected with, discover new games, "
    "or enjoy a quiet solo puzzle.\n\n"
    "Choose your next moment:"
)


@router.message(F.text == "🎮 LikBy Play")
@router.message(Command("play"))
@router.message(Command("games"))
async def play_hub_command(
    message: Message,
    user_repo: UserRepository,
    gaming_entitlement_service: Optional[GamingEntitlementService] = None,
) -> None:
    """Primary entry point to LikBy Play."""
    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url

    quota_line = ""
    if message.from_user and gaming_entitlement_service:
        user = await user_repo.get_by_telegram_id(message.from_user.id)
        if user:
            ent = await gaming_entitlement_service.get_user_entitlements(user.id)
            rem = ent["daily_duels_remaining"]
            lim = ent["daily_duels_limit"]
            lim_str = "Unlimited 👑" if lim == -1 else f"{lim}"
            rem_str = "Unlimited" if rem == -1 else f"{rem}/{lim_str}"
            quota_line = f"\n\n🎯 <b>Today's Duel Allowance:</b> <code>{rem_str}</code> remaining\n🧩 <b>Solo Games:</b> <code>Unlimited</code>"

    await message.answer(
        f"{WELCOME_TEXT}{quota_line}",
        parse_mode="HTML",
        reply_markup=get_play_hub_keyboard(mini_app_url),
    )


@router.message(Command("duels"))
@router.callback_query(F.data == "play:duels")
async def show_duels(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    gaming_entitlement_service: Optional[GamingEntitlementService] = None,
) -> None:
    """Displays the 11 duel games and daily allowance."""
    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url

    tg_id = event.from_user.id if event.from_user else 0
    quota_info = "5 duels/day on Base"
    if user_repo and gaming_entitlement_service and tg_id:
        user = await user_repo.get_by_telegram_id(tg_id)
        if user:
            ent = await gaming_entitlement_service.get_user_entitlements(user.id)
            rem = ent["daily_duels_remaining"]
            lim = ent["daily_duels_limit"]
            lim_str = "Unlimited" if lim == -1 else f"{lim}"
            rem_str = "Unlimited" if rem == -1 else f"{rem}"
            quota_info = f"{rem_str} of {lim_str} duels remaining today"

    duels = [g for g in GAME_CATALOGUE.values() if g.mode in (GameMode.DUEL, GameMode.COOP_DUEL)]
    duel_list_lines = []
    for idx, d in enumerate(duels, 1):
        duel_list_lines.append(f"{idx}. <b>{d.name}</b> — <i>{d.description}</i> ({d.typical_duration})")

    duel_text = (
        "⚔️ <b>LikBy Play — 11 Multiplayer Duels</b>\n\n"
        f"🎯 <b>Your Allowance:</b> {quota_info}\n\n"
        + "\n\n".join(duel_list_lines)
        + "\n\n<i>To start a duel, open LikBy Play or challenge your active chat partner!</i>"
    )

    if isinstance(event, Message):
        await event.answer(duel_text, parse_mode="HTML", reply_markup=get_play_hub_keyboard(mini_app_url))
    else:
        await event.answer()
        if event.message:
            await event.message.edit_text(duel_text, parse_mode="HTML", reply_markup=get_play_hub_keyboard(mini_app_url))


@router.message(Command("solo"))
@router.callback_query(F.data == "play:solo")
async def show_solo(
    event: Message | CallbackQuery,
) -> None:
    """Displays the 6 solo games with unlimited access."""
    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url

    solos = [g for g in GAME_CATALOGUE.values() if g.mode == GameMode.SOLO]
    solo_list_lines = []
    for idx, s in enumerate(solos, 1):
        solo_list_lines.append(f"{idx}. <b>{s.name}</b> — <i>{s.description}</i> ({s.typical_duration})")

    solo_text = (
        "🧩 <b>LikBy Play — 6 Solo Experiences</b>\n\n"
        "✨ <b>Unlimited for all tiers!</b> Solo games do not consume duel credits.\n\n"
        + "\n\n".join(solo_list_lines)
        + "\n\n<i>Play anytime while waiting for a match or relaxing solo.</i>"
    )

    if isinstance(event, Message):
        await event.answer(solo_text, parse_mode="HTML", reply_markup=get_play_hub_keyboard(mini_app_url))
    else:
        await event.answer()
        if event.message:
            await event.message.edit_text(solo_text, parse_mode="HTML", reply_markup=get_play_hub_keyboard(mini_app_url))


@router.callback_query(F.data == "play:catalogue")
async def show_catalogue(
    callback: CallbackQuery,
) -> None:
    """Displays the entire 17-game collection overview."""
    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url
    await callback.answer()

    text = (
        "✨ <b>LikBy Play — Complete 17 Game Catalogue</b> 🩵\n\n"
        "<b>Multiplayer Duels (11 Games):</b>\n"
        "1. 🎱 Carrom Clash (Physics)\n"
        "2. 🏒 Air Rush (Arcade)\n"
        "3. 🎱 Pocket Pool (Precision)\n"
        "4. ⚔️ Stick Arena (Action)\n"
        "5. 🎨 QuickDraw (Drawing & Guessing)\n"
        "6. 🔤 Word Rush (Word Challenge)\n"
        "7. 🧠 Brain Blitz (Trivia)\n"
        "8. ⚡ Reflex Rush (Reaction)\n"
        "9. 🔴 Connect Four (Strategy)\n"
        "10. 💭 MindMatch (Social Discovery)\n"
        "11. 🕵️ Mystery Mission (Co-op Deduction)\n\n"
        "<b>Solo Experiences (6 Games — Unlimited):</b>\n"
        "12. 🧩 Zen Merge (Number logic)\n"
        "13. 🔎 Word Hunt (Word search)\n"
        "14. 🎨 Color Flow (Color logic)\n"
        "15. ⛳ Pocket Golf (Mini golf)\n"
        "16. ⚡ Reflex Lab (Cognitive & focus)\n"
        "17. 🔐 Daily Mystery (Daily riddle)\n\n"
        "<i>Launch LikBy Play to experience them all!</i>"
    )

    if callback.message:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_play_hub_keyboard(mini_app_url))


@router.message(Command("mygames"))
@router.callback_query(F.data == "play:progress")
async def show_mygames(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    play_game_service: Optional[PlayGameService] = None,
    gaming_entitlement_service: Optional[GamingEntitlementService] = None,
) -> None:
    """Displays player statistics and daily allowances."""
    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url

    tg_id = event.from_user.id if event.from_user else 0
    stats_text = "<i>No gameplay records found yet. Play a game to record your statistics!</i>"
    tier_info = "LikBy Base"
    quota_info = "5 duels / day"

    if user_repo and tg_id:
        user = await user_repo.get_by_telegram_id(tg_id)
        if user:
            if gaming_entitlement_service:
                ent = await gaming_entitlement_service.get_user_entitlements(user.id)
                tier_info = ent["tier"].replace("_", " ").title()
                rem = ent["daily_duels_remaining"]
                lim = ent["daily_duels_limit"]
                lim_str = "Unlimited" if lim == -1 else f"{lim}"
                rem_str = "Unlimited" if rem == -1 else f"{rem}"
                quota_info = f"{rem_str} of {lim_str} duels remaining today"

            if play_game_service:
                stats = await play_game_service.get_user_game_statistics(user.id)
                if stats:
                    lines = []
                    for st in stats:
                        lines.append(
                            f"• <b>{st.game_id.replace('_', ' ').title()}:</b> "
                            f"{st.games_played} played, {st.wins} wins, Best: {st.high_score}"
                        )
                    stats_text = "\n".join(lines)

    text = (
        "📊 <b>Your LikBy Play Progress</b>\n\n"
        f"👑 <b>Current Tier:</b> {tier_info}\n"
        f"🎯 <b>Daily Duel Allowance:</b> {quota_info}\n"
        f"🧩 <b>Solo Games:</b> Unlimited\n\n"
        f"<b>Game History & Records:</b>\n{stats_text}\n\n"
        "<i>Open LikBy Play to check out leaderboards and personal achievements!</i>"
    )

    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML", reply_markup=get_play_hub_keyboard(mini_app_url))
    else:
        await event.answer()
        if event.message:
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=get_play_hub_keyboard(mini_app_url))
