"""
tests/unit/test_game.py
Unit tests for server-authoritative Tic-Tac-Toe state machine.
"""

import pytest
from likby.domain.entities.game import (
    GameSession,
    InvalidMoveError,
    NotYourTurnError,
)
from likby.domain.enums import GameStatus


def test_game_creation():
    game = GameSession(
        id="gm_001",
        session_id="ses_001",
        player_x_id="usr_x",
        player_o_id="usr_o",
        current_turn_user_id="usr_x",
    )
    assert game.status == GameStatus.IN_PROGRESS
    assert game.current_turn_user_id == "usr_x"
    assert game.move_count == 0


def test_out_of_turn_move_rejected():
    game = GameSession(
        id="gm_001",
        session_id="ses_001",
        player_x_id="usr_x",
        player_o_id="usr_o",
        current_turn_user_id="usr_x",
    )
    with pytest.raises(NotYourTurnError):
        game.make_move(user_id="usr_o", row=0, col=0)


def test_occupied_cell_move_rejected():
    game = GameSession(
        id="gm_001",
        session_id="ses_001",
        player_x_id="usr_x",
        player_o_id="usr_o",
        current_turn_user_id="usr_x",
    )
    game.make_move(user_id="usr_x", row=1, col=1)
    with pytest.raises(InvalidMoveError):
        game.make_move(user_id="usr_o", row=1, col=1)


def test_player_x_wins_horizontal():
    game = GameSession(
        id="gm_001",
        session_id="ses_001",
        player_x_id="usr_x",
        player_o_id="usr_o",
        current_turn_user_id="usr_x",
    )
    # Move 1: X (0,0)
    game.make_move("usr_x", 0, 0)
    # Move 2: O (1,0)
    game.make_move("usr_o", 1, 0)
    # Move 3: X (0,1)
    game.make_move("usr_x", 0, 1)
    # Move 4: O (1,1)
    game.make_move("usr_o", 1, 1)
    # Move 5: X (0,2) -> X wins row 0
    status, winner = game.make_move("usr_x", 0, 2)

    assert status == GameStatus.COMPLETED
    assert winner == "usr_x"
    assert game.winner_id == "usr_x"


def test_draw_game():
    game = GameSession(
        id="gm_001",
        session_id="ses_001",
        player_x_id="usr_x",
        player_o_id="usr_o",
        current_turn_user_id="usr_x",
    )
    # Sequence to produce a draw:
    # X O X
    # X O O
    # O X X
    moves = [
        ("usr_x", 0, 0), ("usr_o", 0, 1), ("usr_x", 0, 2),
        ("usr_o", 1, 1), ("usr_x", 1, 0), ("usr_o", 1, 2),
        ("usr_x", 2, 1), ("usr_o", 2, 0), ("usr_x", 2, 2),
    ]
    status = GameStatus.IN_PROGRESS
    winner = None
    for player, r, c in moves:
        status, winner = game.make_move(player, r, c)

    assert status == GameStatus.DRAW
    assert winner is None
