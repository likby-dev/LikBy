"""
tikible.telegram.handlers.game
Handlers for multiplayer Tic-Tac-Toe invites, moves, and board updates.
"""

import uuid
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from tikible.domain.entities.game import (
    GameSession,
    InvalidMoveError,
    NotYourTurnError,
)
from tikible.domain.enums import GameStatus
from tikible.repositories.interfaces import (
    ChatSessionRepository,
    GameRepository,
    UserRepository,
)
from tikible.services.chat_relay_service import ChatRelayService
from tikible.telegram.keyboards import get_tictactoe_keyboard
from tikible.telegram.utils import safe_edit_text

router = Router(name="game")


@router.message(F.text == "🎮 Play Game")
@router.message(Command("game"))
async def start_game(
    message: Message,
    user_repo: UserRepository,
    session_repo: ChatSessionRepository,
    game_repo: GameRepository,
    chat_relay: ChatRelayService,
) -> None:
    if not message.from_user:
        return

    tg_id = message.from_user.id
    cached = await chat_relay.get_or_warm_session(tg_id)
    if not cached:
        await message.answer("You must be in an active chat to play Tic-Tac-Toe!")
        return

    # Check for existing active game
    active_game = await game_repo.get_active_by_session_id(cached.session_id)
    if active_game:
        await message.answer(
            "A game is already in progress!",
            reply_markup=get_tictactoe_keyboard(active_game.board, active_game.id),
        )
        return

    # Create new game: Initiator is X (moves first)
    player_x = cached.user_a_id if tg_id == cached.user_a_tg_id else cached.user_b_id
    player_o = cached.get_partner_user_id(player_x)
    partner_tg_id = cached.get_partner_tg_id(tg_id)

    game_id = f"gm_{uuid.uuid4().hex[:12]}"
    game = GameSession(
        id=game_id,
        session_id=cached.session_id,
        player_x_id=player_x,
        player_o_id=player_o,
        current_turn_user_id=player_x,
    )
    await game_repo.save(game)

    kb = get_tictactoe_keyboard(game.board, game.id)

    # Send to initiator
    await message.answer(
        "🎮 <b>Tic-Tac-Toe Started!</b>\n\n"
        "You are <b>❌</b> (Your turn).\nTap a square to move:",
        parse_mode="HTML",
        reply_markup=kb,
    )

    # Send to partner
    await message.bot.send_message(
        chat_id=partner_tg_id,
        text=(
            "🎮 <b>Your partner started Tic-Tac-Toe!</b>\n\n"
            "You are <b>⭕</b> (Waiting for partner's first move):"
        ),
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("ttt_move:"))
async def process_move(
    callback: CallbackQuery,
    user_repo: UserRepository,
    game_repo: GameRepository,
    chat_relay: ChatRelayService,
) -> None:
    if not callback.data or not callback.from_user or not callback.message:
        return

    parts = callback.data.split(":")
    game_id = parts[1]
    row, col = int(parts[2]), int(parts[3])

    game = await game_repo.get_by_id(game_id)
    if not game:
        await callback.answer("Game not found or finished.", show_alert=True)
        return

    tg_id = callback.from_user.id
    user = await user_repo.get_by_telegram_id(tg_id)
    if not user:
        return

    try:
        status, winner = game.make_move(user_id=user.id, row=row, col=col)
        await game_repo.save(game)
    except NotYourTurnError:
        await callback.answer("⏳ It is not your turn yet!", show_alert=True)
        return
    except InvalidMoveError as e:
        await callback.answer(f"⚠️ {str(e)}", show_alert=True)
        return

    await callback.answer()

    # Get cached session for partner notification
    cached = await chat_relay.get_or_warm_session(tg_id)
    partner_tg_id = cached.get_partner_tg_id(tg_id) if cached else None

    updated_kb = get_tictactoe_keyboard(game.board, game.id)

    if status == GameStatus.COMPLETED:
        win_msg_mover = "🏆 <b>Victory! You won the game!</b>"
        win_msg_partner = "😔 <b>Your partner won the game!</b> Good match."
        await safe_edit_text(callback.message, win_msg_mover, parse_mode="HTML", reply_markup=updated_kb)
        if partner_tg_id and callback.bot:
            await callback.bot.send_message(
                chat_id=partner_tg_id,
                text=win_msg_partner,
                parse_mode="HTML",
                reply_markup=updated_kb,
            )
    elif status == GameStatus.DRAW:
        draw_msg = "🤝 <b>It's a draw!</b> Well played by both."
        await safe_edit_text(callback.message, draw_msg, parse_mode="HTML", reply_markup=updated_kb)
        if partner_tg_id and callback.bot:
            await callback.bot.send_message(
                chat_id=partner_tg_id,
                text=draw_msg,
                parse_mode="HTML",
                reply_markup=updated_kb,
            )
    else:
        # Move succeeded, update current player board
        await safe_edit_text(
            callback.message,
            "Move registered! Waiting for partner...",
            reply_markup=updated_kb,
        )
        if partner_tg_id and callback.bot:
            await callback.bot.send_message(
                chat_id=partner_tg_id,
                text="🔔 <b>Your turn in Tic-Tac-Toe!</b>",
                parse_mode="HTML",
                reply_markup=updated_kb,
            )
