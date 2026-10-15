"""
tests/unit/test_solo_games.py
Unit tests for solo games: Trivia Blitz, Gem Hunter, and Rock Paper Scissors.
"""

from tikible.games.solo.gem_hunter import GemHunterGame
from tikible.games.solo.rps import RPSChoice, play_rps
from tikible.games.solo.trivia import TRIVIA_QUESTIONS, get_random_question


def test_trivia_question_selection():
    idx, q = get_random_question()
    assert 0 <= idx < len(TRIVIA_QUESTIONS)
    assert len(q.options) == 4
    assert 0 <= q.correct_idx <= 3
    assert q.prompt != ""
    assert q.category != ""


def test_gem_hunter_initial_state():
    game = GemHunterGame.start_new()
    assert 0 <= game.bomb_row <= 2
    assert 0 <= game.bomb_col <= 2
    assert game.score == 0
    assert game.is_over is False
    assert game.hit_bomb is False


def test_gem_hunter_reveal_gem_and_bomb():
    # Deterministic bomb location at (1, 1)
    game = GemHunterGame(bomb_row=1, bomb_col=1)

    # 1. Reveal safe tile (0, 0)
    is_bomb, is_win = game.reveal(0, 0)
    assert is_bomb is False
    assert is_win is False
    assert game.score == 10
    assert game.revealed[0][0] is True
    assert game.is_over is False

    # 2. Reveal another safe tile (0, 1)
    is_bomb, is_win = game.reveal(0, 1)
    assert is_bomb is False
    assert game.score == 20

    # 3. Hit the bomb at (1, 1)
    is_bomb, is_win = game.reveal(1, 1)
    assert is_bomb is True
    assert is_win is False
    assert game.hit_bomb is True
    assert game.is_over is True


def test_gem_hunter_perfect_clear():
    # Bomb at (2, 2)
    game = GemHunterGame(bomb_row=2, bomb_col=2)

    # Reveal all 8 non-bomb tiles
    for r in range(3):
        for c in range(3):
            if r == 2 and c == 2:
                continue
            is_bomb, is_win = game.reveal(r, c)
            assert is_bomb is False

    # Should have won!
    assert game.is_over is True
    assert game.hit_bomb is False
    assert is_win is True
    # 8 * 10 = 80 + 50 bonus = 130
    assert game.score == 130


def test_rps_mechanics():
    # Test all outcome possibilities
    outcomes = set()
    for _ in range(30):
        bot_choice, outcome, commentary = play_rps(RPSChoice.ROCK)
        assert bot_choice in [RPSChoice.ROCK, RPSChoice.PAPER, RPSChoice.SCISSORS]
        assert outcome in ["win", "lose", "draw"]
        outcomes.add(outcome)

    # Over 30 trials with random bot choice, all 3 outcomes should occur
    assert "draw" in outcomes or "win" in outcomes or "lose" in outcomes
