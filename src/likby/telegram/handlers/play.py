"""
likby.telegram.handlers.play
Telegram Bot interface and entry points for LikBy Play gaming ecosystem.
Handles /play, /games, /duels, /solo, /mygames commands and interactive game menus.
"""

from typing import Any, Optional
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from likby.config import get_settings
from likby.domain.entities.play_game import GAME_CATALOGUE
from likby.domain.enums import GameMode, SubscriptionTier
from likby.repositories.interfaces import UserRepository
from likby.services.gaming_entitlement_service import GamingEntitlementService
from likby.services.play_game_service import PlayGameService
from likby.telegram.keyboards import (
    get_duel_game_card_keyboard,
    get_duel_games_keyboard,
    get_play_hub_keyboard,
    get_solo_game_card_keyboard,
    get_solo_games_keyboard,
)

router = Router(name="play")


WELCOME_TEXT = (
    "<b>Welcome to LikBy Play</b> 🩵\n\n"
    "<i>Every connection has a game. Every game creates a moment.</i>\n\n"
    "Challenge someone you've connected with, discover new games, "
    "or enjoy a quiet solo puzzle.\n\n"
    "Choose your next moment:"
)


@router.message(F.text.in_(["🎮 LikBy Play", "🎮 Games & Arcade", "🎮 Play", "🕹 Solo Arcade"]))
@router.message(Command("play"))
@router.message(Command("games"))
@router.message(Command("arcade"))
@router.callback_query(F.data == "play:hub")
async def play_hub_command(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    gaming_entitlement_service: Optional[GamingEntitlementService] = None,
) -> None:
    """Primary entry point to LikBy Play & Gaming Hub."""
    message = event if isinstance(event, Message) else event.message
    if isinstance(event, CallbackQuery):
        await event.answer()

    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"

    quota_line = ""
    tg_id = event.from_user.id if event.from_user else 0
    if tg_id and user_repo and gaming_entitlement_service:
        user = await user_repo.get_by_telegram_id(tg_id)
        if user:
            ent = await gaming_entitlement_service.get_user_entitlements(user.id)
            rem = ent["daily_duels_remaining"]
            lim = ent["daily_duels_limit"]
            lim_str = "Unlimited 👑" if lim == -1 else f"{lim}"
            rem_str = "Unlimited" if rem == -1 else f"{rem}/{lim_str}"
            quota_line = f"\n\n🎯 <b>Today's Duel Allowance:</b> <code>{rem_str}</code> remaining\n🧩 <b>Solo Games:</b> <code>Unlimited (Free)</code>"

    text = f"{WELCOME_TEXT}{quota_line}"
    kb = get_play_hub_keyboard(mini_app_url)
    if isinstance(event, CallbackQuery) and event.message:
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


DUEL_GAMES_DETAILS = {
    "connect_four": {
        "num": 1,
        "name": "Connect Four",
        "emoji": "🔴",
        "category": "Turn-based Strategy",
        "duration": "2–5 mins",
        "desc": "Drop colored discs into the 7-column vertical grid. Outwit your partner by connecting 4 pieces in a row horizontally, vertically, or diagonally.",
        "rules": [
            "Players take turns dropping one disc per turn into any open column.",
            "Discs fall to the lowest unoccupied space within the chosen column.",
            "First player to form an unbroken horizontal, vertical, or diagonal line of 4 wins!",
        ],
        "reward": "Winning a duel awards +15 Karma and Duel Victory status!",
    },
    "carrom_clash": {
        "num": 2,
        "name": "Carrom Clash",
        "emoji": "🎯",
        "category": "Physics Tabletop",
        "duration": "3–7 mins",
        "desc": "Smooth striker tabletop carrom physics with rebound bank shots, friction mechanics, and official queen covering rules.",
        "rules": [
            "Position your striker on the baseline and choose angle and power.",
            "Pocket your designated pieces (White or Black) into corner pockets.",
            "Pocket and cover the Red Queen to seal maximum victory points!",
        ],
        "reward": "Pocketing the Queen & winning awards +20 Karma!",
    },
    "air_rush": {
        "num": 3,
        "name": "Air Rush",
        "emoji": "🏒",
        "category": "Arcade Air Hockey",
        "duration": "1–3 mins",
        "desc": "High-octane neon air hockey table with responsive paddle collisions and fast kinetic rebounds.",
        "rules": [
            "Control your paddle to defend your goal line.",
            "Smash the puck past your opponent's paddle into their goal.",
            "First player to score 5 goals wins the match!",
        ],
        "reward": "Flawless shutout victory awards Ace Striker badge!",
    },
    "pocket_pool": {
        "num": 4,
        "name": "Pocket Pool",
        "emoji": "🎱",
        "category": "Precision 8-Ball Billiards",
        "duration": "3–8 mins",
        "desc": "Tactical 8-ball billiards with realistic collision angles, cue ball spin control, and smooth felt table physics.",
        "rules": [
            "Break the rack and claim either Solids (1-7) or Stripes (9-15).",
            "Clear all balls of your designated suit into the pockets.",
            "Legally sink the 8-Ball into a called pocket for the win!",
        ],
        "reward": "Victory awards +15 Karma score!",
    },
    "stick_arena": {
        "num": 5,
        "name": "Stick Arena",
        "emoji": "🤺",
        "category": "Platform Martial Action",
        "duration": "1–3 mins",
        "desc": "Fast-paced 2D platform brawler with martial arts combos, dodge rolls, and dynamic arena platforms.",
        "rules": [
            "Time strikes, jump between platforms, and dodge enemy attacks.",
            "Build combo multipliers to unleash powerful knockback strikes.",
            "Deplete the opponent's 100 HP or knock them out of the arena!",
        ],
        "reward": "Arena champion earns +15 Karma standing!",
    },
    "quickdraw": {
        "num": 6,
        "name": "QuickDraw",
        "emoji": "🎨",
        "category": "Real-time Sketch & Guess",
        "duration": "2–5 mins",
        "desc": "One player sketches a secret word on an interactive canvas while the other player guesses in real time.",
        "rules": [
            "Drawer gets a secret prompt and 60 seconds to sketch clues on canvas.",
            "Guesser watches live brushstrokes and types guesses.",
            "Swap roles across 4 rounds for total combined creative score!",
        ],
        "reward": "High synchro score awards Master Sketcher title!",
    },
    "word_rush": {
        "num": 7,
        "name": "Word Rush",
        "emoji": "🔤",
        "category": "Competitive Vocabulary Race",
        "duration": "1–3 mins",
        "desc": "Race head-to-head against a shared 3D acrylic letter tile pool to submit valid dictionary words.",
        "rules": [
            "Scramble valid words using letters from the shared pool.",
            "Longer words and fast submissions award combo multipliers.",
            "Highest cumulative word score when the 90-second timer expires wins!",
        ],
        "reward": "Vocabulary champion earns +10 Karma points!",
    },
    "brain_blitz": {
        "num": 8,
        "name": "Brain Blitz",
        "emoji": "🧠",
        "category": "Esports Trivia Showdown",
        "duration": "2–4 mins",
        "desc": "Head-to-head live quiz battle across pop culture, science, geography, and cinema with secret simultaneous reveals.",
        "rules": [
            "Both players receive the same multiple-choice question simultaneously.",
            "15-second countdown per question — faster correct answers earn streak bonuses.",
            "Player with the highest score after 5 questions wins!",
        ],
        "reward": "Perfect 5/5 score awards Grandmaster Scholar badge!",
    },
    "reflex_rush": {
        "num": 9,
        "name": "Reflex Rush",
        "emoji": "⚡️",
        "category": "Millisecond Reaction Chamber",
        "duration": "30–90 secs",
        "desc": "High-tension reaction chamber testing neuro-kinetic tap speed with strict false-start penalties.",
        "rules": [
            "Hold steady during the red anticipation phase (1.5s to 4.0s random delay).",
            "The instant the chamber flashes GREEN, tap immediately!",
            "Fastest valid reaction time across 5 rounds wins the duel.",
        ],
        "reward": "Sub-180ms reaction time awards Lightning Reflexes title!",
    },
    "mindmatch": {
        "num": 10,
        "name": "MindMatch",
        "emoji": "💭",
        "category": "Social Discovery & Harmony",
        "duration": "2–4 mins",
        "desc": "Discover romantic and social compatibility! Both players secretly answer intriguing prompts to calculate harmony score.",
        "rules": [
            "Read the scenario or dilemma (travel, lifestyle, evening vibes, values).",
            "Choose your authentic preference between Option A and Option B.",
            "Reveal synced answers and compute your match percentage (0% to 100%)!",
        ],
        "reward": "80%+ Harmony unlocks Soul Connection achievement!",
    },
    "mystery_mission": {
        "num": 11,
        "name": "Mystery Mission",
        "emoji": "🔍",
        "category": "Co-op Cyber Escape Room",
        "duration": "3–7 mins",
        "desc": "A cooperative mystery escape console! Both partners receive complementary half-clues that must be combined to crack ciphers.",
        "rules": [
            "Player 1 receives Clue A; Player 2 receives Clue B in chat.",
            "Communicate and combine your clue fragments together.",
            "Enter the decrypted 4-digit master code to unlock the safe!",
        ],
        "reward": "Cracking the safe awards +20 Karma to both partners!",
    },
}

DUEL_NUM_MAP = {
    "connect four": "connect_four",
    "c4": "connect_four",
    "carrom": "carrom_clash",
    "carrom clash": "carrom_clash",
    "air rush": "air_rush",
    "hockey": "air_rush",
    "pool": "pocket_pool",
    "pocket pool": "pocket_pool",
    "stick": "stick_arena",
    "stick arena": "stick_arena",
    "draw": "quickdraw",
    "quickdraw": "quickdraw",
    "word rush": "word_rush",
    "trivia": "brain_blitz",
    "brain blitz": "brain_blitz",
    "reflex rush": "reflex_rush",
    "mindmatch": "mindmatch",
    "mystery mission": "mystery_mission",
    "coop": "mystery_mission",
}


def format_duel_card(info: dict, mini_app_url: str, quota_info: str = "") -> str:
    rules_text = "\n".join(f"• {r}" for r in info["rules"])
    quota_header = f"🎯 <b>Daily Duel Allowance:</b> {quota_info}\n" if quota_info else ""
    return (
        f"{info['emoji']} <b>{info['name']} — Multiplayer Duel #{info['num']}</b> ⚔️\n\n"
        f"🌟 <b>Genre:</b> {info['category']}\n"
        f"⏱ <b>Duration:</b> {info['duration']} (Head-to-head)\n"
        f"{quota_header}\n"
        f"📖 <b>About the Duel:</b>\n"
        f"{info['desc']}\n\n"
        f"🎮 <b>How to Play:</b>\n"
        f"{rules_text}\n\n"
        f"🏆 <b>Victory Rewards:</b> {info['reward']}\n\n"
        f"👉 <i>Select an action below to challenge your partner or launch LikBy Play!</i>"
    )


@router.message(Command("duels"))
@router.callback_query(F.data == "play:duels")
async def show_duels(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    gaming_entitlement_service: Optional[GamingEntitlementService] = None,
) -> None:
    """Displays the 11 duel games with dedicated interactive selection buttons."""
    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"

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

    duel_text = (
        "⚔️ <b>LikBy Play — 11 Multiplayer Duels</b>\n\n"
        f"🎯 <b>Your Allowance:</b> {quota_info}\n"
        "<i>Duels unlock live with your chat partner or practice vs AI!</i>\n\n"
        "1. 🔴 <b>Connect Four</b> — <i>Align 4 discs in 7x6 grid</i>\n"
        "2. 🎯 <b>Carrom Clash</b> — <i>Striker physics & Queen rules</i>\n"
        "3. 🏒 <b>Air Rush</b> — <i>Fast-paced kinetic air hockey</i>\n"
        "4. 🎱 <b>Pocket Pool</b> — <i>8-Ball billiards & cue physics</i>\n"
        "5. 🤺 <b>Stick Arena</b> — <i>Martial combat platform brawler</i>\n"
        "6. 🎨 <b>QuickDraw</b> — <i>Real-time sketch & guess race</i>\n"
        "7. 🔤 <b>Word Rush</b> — <i>Shared letter pool vocabulary race</i>\n"
        "8. 🧠 <b>Brain Blitz</b> — <i>Simultaneous esports trivia battle</i>\n"
        "9. ⚡️ <b>Reflex Rush</b> — <i>Sub-180ms reaction test chamber</i>\n"
        "10. 💭 <b>MindMatch</b> — <i>Social compatibility & harmony</i>\n"
        "11. 🔍 <b>Mystery Mission</b> — <i>Co-op escape room clues</i>\n\n"
        "👉 <b>Tap any game button below to select and view rules or challenge!</b>"
    )

    kb = get_duel_games_keyboard(mini_app_url)
    if isinstance(event, Message):
        await event.answer(duel_text, parse_mode="HTML", reply_markup=kb)
    else:
        await event.answer()
        if event.message:
            await event.message.edit_text(duel_text, parse_mode="HTML", reply_markup=kb)


SOLO_GAMES_DETAILS = {
    "zen_merge": {
        "num": 1,
        "name": "Zen Merge (2048)",
        "emoji": "🧘",
        "category": "Sliding Number Puzzle",
        "duration": "3-5 mins",
        "desc": (
            "Immerse yourself in a soothing yet challenging logic puzzle. "
            "Slide numbered tiles across a sleek 4x4 matrix, merging matching numbers to double their value (2+2=4, 4+4=8... 1024+1024=2048). "
            "Features silky smooth sliding animations, haptics, and relaxing ambient audio harmonics."
        ),
        "rules": [
            "Swipe or tap directions (Up, Down, Left, Right) to glide all tiles.",
            "Identical adjacent tiles merge on impact.",
            "Keep the matrix clear and aim for the legendary 2048 tile!",
        ],
        "reward": "Earn up to +15 Karma score for reaching 1024 / 2048 milestones!",
    },
    "word_hunt": {
        "num": 2,
        "name": "Word Hunt",
        "emoji": "🔤",
        "category": "Lexicon Matrix Search",
        "duration": "2-4 mins",
        "desc": (
            "Sharpen your vocabulary and lateral acuity! "
            "Scour a 5x5 matrix of acrylic letter tiles for hidden high-scoring words hidden across rows, columns, and diagonal angles."
        ),
        "rules": [
            "Spot valid English words formed in the matrix.",
            "Tap the letters in sequence to build your word.",
            "Press Claim to bank points and reveal hidden bonus keywords!",
        ],
        "reward": "Complete a 5-word matrix for +5 Karma score!",
    },
    "color_flow": {
        "num": 3,
        "name": "Color Flow",
        "emoji": "🎨",
        "category": "Topological Path Puzzle",
        "duration": "2-3 mins",
        "desc": (
            "A mesmerizing test of spatial logic and fluid dynamics. "
            "Connect pairs of matching glowing neon color dots by drawing continuous conduits across the board without overlapping paths."
        ),
        "rules": [
            "Drag lines to connect matching color pairs (Cyan, Pink, Amber).",
            "Fill all tiles on the board with flowing color lines.",
            "Paths must never intersect or break connection.",
        ],
        "reward": "100% flow coverage awards Color Master achievement!",
    },
    "pocket_golf": {
        "num": 4,
        "name": "Pocket Golf",
        "emoji": "⛳️",
        "category": "Precision Physics Minigolf",
        "duration": "2-3 mins",
        "desc": (
            "Step up to the miniature links! Gauge speed, friction, angles, and sand traps "
            "to guide your golf ball around tricky obstacles and sink it in the cup with minimal strokes."
        ),
        "rules": [
            "Choose between precision Tap Putt or high-power Long Drive.",
            "Evade sand bunkers and water hazards that slow down your ball.",
            "Sink the ball into the cup under par for maximum score!",
        ],
        "reward": "Hole-in-one grants +10 Karma and Ace Golfer title!",
    },
    "reflex_lab": {
        "num": 5,
        "name": "Reflex Lab",
        "emoji": "⚡️",
        "category": "Neuro Speed Trainer",
        "duration": "1-2 mins",
        "desc": (
            "A fast-paced neuro-speed trainer! Kinetic glowing neon orbs appear at random intervals. "
            "Tap as quickly as possible upon appearance to log your millisecond reaction speed."
        ),
        "rules": [
            "Focus your vision on the matrix.",
            "As soon as the kinetic neon orb flashes, tap it instantly!",
            "Multiple rounds track your consistency and personal record.",
        ],
        "reward": "Sub-200ms reaction times award Elite Reflex badge!",
    },
    "daily_mystery": {
        "num": 6,
        "name": "Daily Mystery",
        "emoji": "🔍",
        "category": "Cryptic Deduction Riddle",
        "duration": "2-5 mins",
        "desc": (
            "A daily dose of lateral thinking and cryptic mystery! "
            "Read the daily encrypted clue, deduce the hidden solution, and enter your answer to unlock the mystery safe."
        ),
        "rules": [
            "Read today's featured cryptic riddle.",
            "Connect the hidden clues to deduce the answer.",
            "Type your guess directly in chat or unlock inside LikBy Play!",
        ],
        "reward": "Daily correct solve awards +10 Karma standing!",
    },
}

SOLO_NUM_MAP = {
    "1": "zen_merge",
    "2": "word_hunt",
    "3": "color_flow",
    "4": "pocket_golf",
    "5": "reflex_lab",
    "6": "daily_mystery",
    "zen": "zen_merge",
    "zen merge": "zen_merge",
    "2048": "zen_merge",
    "word": "word_hunt",
    "word hunt": "word_hunt",
    "color": "color_flow",
    "color flow": "color_flow",
    "golf": "pocket_golf",
    "pocket golf": "pocket_golf",
    "reflex": "reflex_lab",
    "reflex lab": "reflex_lab",
    "mystery": "daily_mystery",
    "daily mystery": "daily_mystery",
}


def format_solo_card(info: dict, mini_app_url: str) -> str:
    rules_text = "\n".join(f"• {r}" for r in info["rules"])
    return (
        f"{info['emoji']} <b>{info['name']} — Solo Game #{info['num']}</b> ✨\n\n"
        f"🌟 <b>Genre:</b> {info['category']}\n"
        f"⏱ <b>Duration:</b> {info['duration']} (Play anytime solo!)\n"
        f"🎯 <b>Status:</b> <code>100% Free & Unlimited (Zero session needed)</code>\n\n"
        f"📖 <b>About the Game:</b>\n"
        f"{info['desc']}\n\n"
        f"🎮 <b>How to Play:</b>\n"
        f"{rules_text}\n\n"
        f"🏆 <b>Rewards:</b> {info['reward']}\n\n"
        f"👉 <i>Tap <b>🚀 Play Now</b> below to launch directly in LikBy Play!</i>"
    )


@router.message(Command("solo"))
@router.callback_query(F.data.in_(["play:solo", "play:solo_info", "solo:hub"]))
async def show_solo(
    event: Message | CallbackQuery,
) -> None:
    """Displays the 6 solo games with unlimited access and dedicated launcher buttons."""
    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"

    solo_text = (
        "🧩 <b>LikBy Play — 6 Solo Experiences</b>\n\n"
        "✨ <b>100% Free & Unlimited for all tiers!</b>\n"
        "<i>Solo games never consume duel quota and do NOT require an active chat session.</i>\n\n"
        "1. 🧘 <b>Zen Merge (2048)</b> — <i>Sliding tile puzzle (Goal: 2048)</i>\n"
        "2. 🔤 <b>Word Hunt</b> — <i>5x5 matrix vocabulary search</i>\n"
        "3. 🎨 <b>Color Flow</b> — <i>Connect matching neon paths</i>\n"
        "4. ⛳️ <b>Pocket Golf</b> — <i>Precision slingshot mini-golf</i>\n"
        "5. ⚡️ <b>Reflex Lab</b> — <i>Sub-200ms neuro speed test</i>\n"
        "6. 🔍 <b>Daily Mystery</b> — <i>Cryptic lateral riddles & secrets</i>\n\n"
        "👉 <b>Tap any game button below or type its number (1-6) to play instantly!</b>"
    )

    kb = get_solo_games_keyboard(mini_app_url)
    if isinstance(event, Message):
        await event.answer(solo_text, parse_mode="HTML", reply_markup=kb)
    else:
        await event.answer()
        if event.message:
            await event.message.edit_text(solo_text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("play:solo_card:"))
async def solo_game_card_callback(
    callback: CallbackQuery,
) -> None:
    """Renders the detailed game card for a specific solo game."""
    if not callback.data:
        return
    game_id = callback.data.split("play:solo_card:")[1]
    info = SOLO_GAMES_DETAILS.get(game_id)
    if not info:
        await callback.answer("Game not found", show_alert=True)
        return
    await callback.answer()
    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"
    text = format_solo_card(info, mini_app_url)
    kb = get_solo_game_card_keyboard(game_id, mini_app_url)
    if callback.message:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("play:duel_card:"))
async def duel_game_card_callback(
    callback: CallbackQuery,
    user_repo: UserRepository,
    chat_relay: Optional[Any] = None,
    gaming_entitlement_service: Optional[GamingEntitlementService] = None,
) -> None:
    """Renders the detailed game card for a specific duel game with challenge buttons."""
    if not callback.data:
        return
    game_id = callback.data.split("play:duel_card:")[1]
    info = DUEL_GAMES_DETAILS.get(game_id)
    if not info:
        await callback.answer("Duel game not found", show_alert=True)
        return
    await callback.answer()

    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"

    tg_id = callback.from_user.id if callback.from_user else 0
    in_active = False
    quota_info = "5 duels/day on Base"
    if chat_relay and tg_id:
        active_session = await chat_relay.get_or_warm_session(tg_id)
        in_active = active_session is not None

    if user_repo and gaming_entitlement_service and tg_id:
        user = await user_repo.get_by_telegram_id(tg_id)
        if user:
            ent = await gaming_entitlement_service.get_user_entitlements(user.id)
            rem = ent["daily_duels_remaining"]
            lim = ent["daily_duels_limit"]
            lim_str = "Unlimited" if lim == -1 else f"{lim}"
            rem_str = "Unlimited" if rem == -1 else f"{rem}"
            quota_info = f"{rem_str} of {lim_str} duels remaining"

    text = format_duel_card(info, mini_app_url, quota_info)
    kb = get_duel_game_card_keyboard(game_id, mini_app_url, in_active_session=in_active)
    if callback.message:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("duel:practice:"))
async def duel_practice_callback(
    callback: CallbackQuery,
) -> None:
    """Launches AI practice arena for a duel game."""
    if not callback.data:
        return
    game_id = callback.data.split("duel:practice:")[1]
    info = DUEL_GAMES_DETAILS.get(game_id)
    game_name = info["name"] if info else game_id.replace("_", " ").title()
    await callback.answer()

    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"
    clean_base = mini_app_url.split("?")[0].rstrip("/")
    game_url = f"{clean_base}?game={game_id}&practice=1"

    text = (
        f"🤖 <b>AI Practice Arena — {game_name}</b>\n\n"
        "Sharpen your skills against the LikBy Practice Bot! "
        "Practice matches do not consume daily duel credits.\n\n"
        "👉 <i>Tap <b>Launch Practice Arena</b> below to begin!</i>"
    )
    rows = []
    if mini_app_url and mini_app_url.startswith("https://"):
        rows.append([
            InlineKeyboardButton(text="🚀 Launch Practice Arena (Mini App)", web_app=WebAppInfo(url=game_url))
        ])
    rows.append([
        InlineKeyboardButton(text=f"« Back to {game_name}", callback_data=f"play:duel_card:{game_id}"),
        InlineKeyboardButton(text="« All 11 Duels", callback_data="play:duels"),
    ])
    if callback.message:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("duel:invite:"))
async def duel_invite_callback(
    callback: CallbackQuery,
    chat_relay: Optional[Any] = None,
    bot: Optional[Bot] = None,
) -> None:
    """Challenges the user's active conversation partner to this duel game."""
    if not callback.data or not callback.from_user:
        return
    game_id = callback.data.split("duel:invite:")[1]
    info = DUEL_GAMES_DETAILS.get(game_id)
    game_name = info["name"] if info else game_id.replace("_", " ").title()

    if not chat_relay:
        await callback.answer("Chat service unavailable.", show_alert=True)
        return

    session = await chat_relay.get_or_warm_session(callback.from_user.id)
    if not session:
        await callback.answer("You are not currently in an active chat session.", show_alert=True)
        return

    partner_tg_id = session.user2_tg_id if session.user1_tg_id == callback.from_user.id else session.user1_tg_id

    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"
    clean_base = mini_app_url.split("?")[0].rstrip("/")
    duel_url = f"{clean_base}?game={game_id}&partner_id={callback.from_user.id}&session_id={session.id}"

    if bot:
        partner_btn = (
            InlineKeyboardButton(text=f"⚔️ Accept {game_name} Duel", web_app=WebAppInfo(url=duel_url))
            if mini_app_url and mini_app_url.startswith("https://")
            else InlineKeyboardButton(text=f"⚔️ Accept {game_name} Duel", callback_data=f"play:duel_card:{game_id}")
        )
        partner_kb = InlineKeyboardMarkup(inline_keyboard=[[partner_btn]])
        try:
            await bot.send_message(
                chat_id=partner_tg_id,
                text=f"⚔️ <b>Your partner has challenged you to {game_name}!</b>\n\n<i>Tap below to accept and enter the match:</i>",
                parse_mode="HTML",
                reply_markup=partner_kb,
            )
        except Exception:
            pass

    await callback.answer(f"⚔️ Challenge sent for {game_name}!", show_alert=True)


async def not_in_active_session_filter(message: Message, chat_relay: Optional[Any] = None) -> bool:
    """Filter that matches ONLY when the user is NOT in an active conversation session."""
    if not message.from_user:
        return False
    if not chat_relay:
        return True
    try:
        active_session = await chat_relay.get_or_warm_session(message.from_user.id)
        return active_session is None
    except Exception:
        return True


COMBINED_GAMES_MAP = {**SOLO_NUM_MAP, **DUEL_NUM_MAP}


@router.message(F.text.in_(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]), not_in_active_session_filter)
@router.message(F.text.lower().in_(list(COMBINED_GAMES_MAP.keys())), not_in_active_session_filter)
async def handle_solo_number_shortcut(
    message: Message,
    chat_relay: Optional[Any] = None,
    user_repo: Optional[UserRepository] = None,
    gaming_entitlement_service: Optional[GamingEntitlementService] = None,
) -> None:
    """Instantly launches or shows game card when typing number or game name outside chat."""
    text_clean = (message.text or "").strip().lower()
    settings = get_settings()
    mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"

    # Check solo games first
    if text_clean in SOLO_NUM_MAP:
        game_id = SOLO_NUM_MAP[text_clean]
        info = SOLO_GAMES_DETAILS.get(game_id)
        if info:
            text = format_solo_card(info, mini_app_url)
            kb = get_solo_game_card_keyboard(game_id, mini_app_url)
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
            return

    # Check duel games
    if text_clean in DUEL_NUM_MAP:
        game_id = DUEL_NUM_MAP[text_clean]
        info = DUEL_GAMES_DETAILS.get(game_id)
        if info:
            text = format_duel_card(info, mini_app_url)
            kb = get_duel_game_card_keyboard(game_id, mini_app_url, in_active_session=False)
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
            return



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
