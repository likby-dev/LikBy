"""
tikible.telegram.handlers.solo_games
Handlers for casual single-player mini-games (Trivia Blitz, Gem Hunter, Rock Paper Scissors)
playable in the matchmaking wait queue or at the main menu.
"""

from typing import Dict
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from tikible.games.solo.gem_hunter import GemHunterGame
from tikible.games.solo.rps import CHOICE_EMOJIS, RPSChoice, play_rps
from tikible.games.solo.trivia import TRIVIA_QUESTIONS, get_random_question
from tikible.telegram.keyboards import (
    get_gem_hunter_keyboard,
    get_rps_keyboard,
    get_solo_hub_keyboard,
    get_trivia_keyboard,
)

router = Router(name="solo_games")

# In-memory session stores for active casual games keyed by user telegram_id
_USER_GEM_GAMES: Dict[int, GemHunterGame] = {}
_USER_TRIVIA_STREAKS: Dict[int, int] = {}
_USER_RPS_SCORES: Dict[int, Dict[str, int]] = {}  # tg_id -> {"wins": 0, "losses": 0, "draws": 0}


@router.message(F.text == "🕹 Solo Arcade")
@router.message(Command("arcade"))
@router.message(Command("games"))
async def open_arcade_menu(message: Message) -> None:
    """Entrypoint to solo games arcade."""
    await message.answer(
        "🕹 <b>Welcome to LikBy Solo Arcade!</b>\n\n"
        "Play quick, fun casual games while waiting for a conversation partner or during your downtime:\n\n"
        "• 🎯 <b>Trivia Blitz</b> — Test your knowledge across pop culture, tech, and science.\n"
        "• 💎 <b>Gem Hunter</b> — 3x3 Mini Minesweeper. Uncover gems without triggering the bomb!\n"
        "• 🪨 <b>Rock Paper Scissors</b> — Quick rounds against the bot.\n\n"
        "<i>Select a game below to begin:</i>",
        parse_mode="HTML",
        reply_markup=get_solo_hub_keyboard(),
    )


@router.callback_query(F.data == "solo:hub")
async def back_to_arcade_hub(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.message:
        return
    await callback.message.edit_text(
        "🕹 <b>LikBy Solo Arcade</b>\n\n"
        "Choose a casual game to play:",
        parse_mode="HTML",
        reply_markup=get_solo_hub_keyboard(),
    )


@router.callback_query(F.data == "solo:close")
async def close_arcade(callback: CallbackQuery) -> None:
    await callback.answer("Arcade closed.")
    if callback.message:
        await callback.message.delete()


# ============================================================================
# TRIVIA BLITZ
# ============================================================================

@router.callback_query(F.data == "solo:trivia:new")
async def start_new_trivia(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    q_idx, question = get_random_question()
    streak = _USER_TRIVIA_STREAKS.get(callback.from_user.id, 0)

    kb = get_trivia_keyboard(q_idx, question.options)
    await callback.message.edit_text(
        f"🎯 <b>Trivia Blitz</b> ({question.category})\n"
        f"🔥 <i>Current Streak: {streak}</i>\n\n"
        f"<b>{question.prompt}</b>",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("trivia_ans:"))
async def process_trivia_answer(callback: CallbackQuery) -> None:
    if not callback.data or not callback.from_user or not callback.message:
        return

    parts = callback.data.split(":")
    q_idx = int(parts[1])
    selected_opt = int(parts[2])

    if q_idx >= len(TRIVIA_QUESTIONS):
        await callback.answer("Question expired.", show_alert=True)
        return

    question = TRIVIA_QUESTIONS[q_idx]
    is_correct = selected_opt == question.correct_idx
    tg_id = callback.from_user.id

    if is_correct:
        _USER_TRIVIA_STREAKS[tg_id] = _USER_TRIVIA_STREAKS.get(tg_id, 0) + 1
        streak = _USER_TRIVIA_STREAKS[tg_id]
        verdict = f"✅ <b>Brilliant! That is CORRECT!</b> (+10 pts)\n🔥 Streak: <b>{streak}</b>"
    else:
        _USER_TRIVIA_STREAKS[tg_id] = 0
        correct_answer = question.options[question.correct_idx]
        verdict = (
            f"❌ <b>Not quite!</b>\n"
            f"The correct answer was: <b>{correct_answer}</b>\n"
            f"Streak reset to 0."
        )

    await callback.answer("Correct!" if is_correct else "Incorrect!")

    next_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Next Question", callback_data="solo:trivia:new")],
            [InlineKeyboardButton(text="🏠 Solo Arcade", callback_data="solo:hub")],
        ]
    )

    await callback.message.edit_text(
        f"🎯 <b>Trivia Blitz</b>\n\n"
        f"<b>Q:</b> {question.prompt}\n\n"
        f"{verdict}",
        parse_mode="HTML",
        reply_markup=next_kb,
    )


# ============================================================================
# GEM HUNTER (MINI MINESWEEPER)
# ============================================================================

@router.callback_query(F.data == "solo:gem:new")
async def start_gem_hunter(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    tg_id = callback.from_user.id
    game = GemHunterGame.start_new()
    _USER_GEM_GAMES[tg_id] = game

    kb = get_gem_hunter_keyboard(game)
    await callback.message.edit_text(
        "💎 <b>Gem Hunter (3x3 Minefield)</b>\n\n"
        "8 tiles hide precious gems 💎 (+10 pts each).\n"
        "1 tile hides a hidden explosive bomb 💣!\n\n"
        "Tap a tile to reveal it. You can cash out anytime!",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("gem_pick:"))
async def process_gem_pick(callback: CallbackQuery) -> None:
    if not callback.data or not callback.from_user or not callback.message:
        return

    parts = callback.data.split(":")
    row, col = int(parts[1]), int(parts[2])
    tg_id = callback.from_user.id

    game = _USER_GEM_GAMES.get(tg_id)
    if not game or game.is_over:
        await callback.answer("Game finished! Start a new one.", show_alert=True)
        return

    is_bomb, is_win = game.reveal(row, col)

    if is_bomb:
        await callback.answer("💥 BOOM! You hit the bomb!", show_alert=True)
        kb = get_gem_hunter_keyboard(game, show_all=True)
        await callback.message.edit_text(
            f"💥 <b>BOOM! Game Over!</b>\n\n"
            f"You struck the hidden explosive. Score for this run: <b>0 pts</b>.\n"
            "Try again and see how many gems you can collect before cashing out!",
            parse_mode="HTML",
            reply_markup=kb,
        )
    elif is_win:
        await callback.answer("🏆 JACKPOT! All gems cleared!", show_alert=True)
        kb = get_gem_hunter_keyboard(game, show_all=True)
        await callback.message.edit_text(
            f"🏆 <b>PERFECT CLEAR! JACKPOT!</b>\n\n"
            f"You successfully gathered all 8 gems without detonating the bomb!\n"
            f"Total Points: <b>{game.score} pts</b> 🌟",
            parse_mode="HTML",
            reply_markup=kb,
        )
    else:
        await callback.answer("💎 Gem Found! +10 pts")
        kb = get_gem_hunter_keyboard(game)
        revealed_count = sum(sum(1 for c in r if c) for r in game.revealed)
        await callback.message.edit_text(
            f"💎 <b>Gems Collected: {revealed_count} / 8</b>\n"
            f"💰 Current Bank: <b>{game.score} pts</b>\n\n"
            "Keep digging or tap <b>Cash Out</b> to bank your score!",
            parse_mode="HTML",
            reply_markup=kb,
        )


@router.callback_query(F.data == "gem:cashout")
async def process_gem_cashout(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        return

    tg_id = callback.from_user.id
    game = _USER_GEM_GAMES.get(tg_id)
    if not game or game.is_over:
        await callback.answer("No active game to cash out.")
        return

    game.is_over = True
    await callback.answer(f"💰 Cashed out {game.score} points!", show_alert=True)
    kb = get_gem_hunter_keyboard(game, show_all=True)
    await callback.message.edit_text(
        f"💰 <b>Cashed Out Successfully!</b>\n\n"
        f"You safely walked away with <b>{game.score} pts</b>! 💎\n"
        f"Smart move avoiding the bomb at row {game.bomb_row + 1}, col {game.bomb_col + 1}.",
        parse_mode="HTML",
        reply_markup=kb,
    )


# ============================================================================
# ROCK, PAPER, SCISSORS
# ============================================================================

@router.callback_query(F.data == "solo:rps:new")
async def start_rps(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return

    tg_id = callback.from_user.id
    stats = _USER_RPS_SCORES.setdefault(tg_id, {"wins": 0, "losses": 0, "draws": 0})
    kb = get_rps_keyboard()

    await callback.message.edit_text(
        "🪨 <b>Rock, Paper, Scissors vs Bot</b>\n\n"
        f"📊 Record: <b>{stats['wins']}W - {stats['losses']}L - {stats['draws']}D</b>\n\n"
        "Choose your move:",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("rps_play:"))
async def process_rps_play(callback: CallbackQuery) -> None:
    if not callback.data or not callback.from_user or not callback.message:
        return

    choice_str = callback.data.split(":")[1]
    user_choice = RPSChoice(choice_str)
    tg_id = callback.from_user.id

    stats = _USER_RPS_SCORES.setdefault(tg_id, {"wins": 0, "losses": 0, "draws": 0})
    bot_choice, outcome, commentary = play_rps(user_choice)

    if outcome == "win":
        stats["wins"] += 1
        header = "🎉 <b>YOU WON!</b>"
    elif outcome == "lose":
        stats["losses"] += 1
        header = "🤖 <b>BOT WON!</b>"
    else:
        stats["draws"] += 1
        header = "🤝 <b>TIE GAME!</b>"

    await callback.answer(f"Bot chose {CHOICE_EMOJIS[bot_choice]}!")

    next_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Play Again", callback_data="solo:rps:new")],
            [InlineKeyboardButton(text="🏠 Solo Arcade", callback_data="solo:hub")],
        ]
    )

    await callback.message.edit_text(
        f"{header}\n\n"
        f"You chose: <b>{CHOICE_EMOJIS[user_choice]}</b>\n"
        f"Bot chose: <b>{CHOICE_EMOJIS[bot_choice]}</b>\n\n"
        f"<i>{commentary}</i>\n\n"
        f"📊 Record: <b>{stats['wins']}W - {stats['losses']}L - {stats['draws']}D</b>",
        parse_mode="HTML",
        reply_markup=next_kb,
    )
