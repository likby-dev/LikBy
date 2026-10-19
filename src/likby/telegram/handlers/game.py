"""
likby.telegram.handlers.game
Handlers for multiplayer Tic-Tac-Toe invites, moves, and board updates.
"""

import uuid
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, WebAppInfo
from likby.config import get_settings
from likby.domain.entities.game import (
    GameSession,
    InvalidMoveError,
    NotYourTurnError,
)
from likby.domain.enums import GameStatus
from likby.repositories.interfaces import (
    ChatSessionRepository,
    GameRepository,
    UserRepository,
)
from likby.services.chat_relay_service import ChatRelayService
from likby.telegram.keyboards import get_chat_duel_invite_keyboard, get_play_hub_keyboard, get_tictactoe_keyboard
from likby.telegram.utils import safe_edit_text

router = Router(name="game")


@router.message(F.text == "🎮 Play Game")
@router.message(Command("game"))
@router.callback_query(F.data == "chat:game")
async def start_game(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    session_repo: ChatSessionRepository,
    game_repo: GameRepository,
    chat_relay: ChatRelayService,
) -> None:
    message = event if isinstance(event, Message) else event.message
    if isinstance(event, CallbackQuery):
        await event.answer()

    if not event.from_user:
        return

    tg_id = event.from_user.id
    cached = await chat_relay.get_or_warm_session(tg_id)
    if not cached:
        settings = get_settings()
        mini_app_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"
        await message.answer(
            "⚔️ <b>Multiplayer Duels require an active conversation partner!</b>\n\n"
            "• Connect with an anonymous conversation partner via <b>🎲 Find Match</b> to duel live in chat!\n"
            "• Or enjoy our <b>6 unlimited Solo Games</b> right now in the <b>LikBy Play App</b>:",
            parse_mode="HTML",
            reply_markup=get_play_hub_keyboard(mini_app_url),
        )
        return

    settings = get_settings()
    base_play_url = settings.telegram_mini_app_url or f"{settings.base_url.rstrip('/')}/play/"

    player_x = cached.user_a_id if tg_id == cached.user_a_tg_id else cached.user_b_id
    player_o = cached.get_partner_user_id(player_x)
    partner_tg_id = cached.get_partner_tg_id(tg_id)

    duel_url = f"{base_play_url}?session_id={cached.session_id}&partner_id={player_o}&mode=duel"
    partner_duel_url = f"{base_play_url}?session_id={cached.session_id}&partner_id={player_x}&mode=duel"

    duel_kb = get_chat_duel_invite_keyboard(duel_url)
    partner_duel_kb = get_chat_duel_invite_keyboard(partner_duel_url)

    # Send to initiator
    await message.answer(
        "⚔️ <b>LikBy Play — Multiplayer Duel Arena</b>\n\n"
        "You are connected with an active partner!\n"
        "Tap below to launch any of the 11 real-time duel games:\n"
        "• Connect Four • Carrom Clash • Air Rush\n"
        "• Pocket Pool • Stick Arena • QuickDraw & more!",
        parse_mode="HTML",
        reply_markup=duel_kb,
    )

    # Send to partner
    await message.bot.send_message(
        chat_id=partner_tg_id,
        text=(
            "⚔️ <b>Your partner invited you to a Duel in LikBy Play!</b>\n\n"
            "Tap below to enter the live game arena with your partner:"
        ),
        parse_mode="HTML",
        reply_markup=partner_duel_kb,
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
