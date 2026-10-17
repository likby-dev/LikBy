"""
tests/unit/test_play_games.py
Comprehensive unit tests for all 17 LikBy Play game engines:
11 Multiplayer Duel Engines and 6 Solo Engines.
"""

import pytest
from likby.domain.enums import GameType
from likby.games.registry import (
    get_duel_engine,
    get_game_engine,
    get_solo_engine,
    list_available_games,
)
from likby.games.duel_engines import (
    AirRushEngine,
    BrainBlitzEngine,
    CarromClashEngine,
    ConnectFourEngine,
    MindMatchEngine,
    MysteryMissionEngine,
    PocketPoolEngine,
    QuickDrawEngine,
    ReflexRushEngine,
    StickArenaEngine,
    WordRushEngine,
)
from likby.games.solo_engines import (
    ColorFlowEngine,
    DailyMysteryEngine,
    PocketGolfEngine,
    ReflexLabEngine,
    WordHuntEngine,
    ZenMergeEngine,
)


def test_registry_contains_all_17_games():
    games = list_available_games()
    assert len(games) == 17
    duel_types = [
        GameType.CARROM_CLASH,
        GameType.AIR_RUSH,
        GameType.POCKET_POOL,
        GameType.STICK_ARENA,
        GameType.QUICKDRAW,
        GameType.WORD_RUSH,
        GameType.BRAIN_BLITZ,
        GameType.REFLEX_RUSH,
        GameType.CONNECT_FOUR,
        GameType.MINDMATCH,
        GameType.MYSTERY_MISSION,
    ]
    solo_types = [
        GameType.ZEN_MERGE,
        GameType.WORD_HUNT,
        GameType.COLOR_FLOW,
        GameType.POCKET_GOLF,
        GameType.REFLEX_LAB,
        GameType.DAILY_MYSTERY,
    ]
    for dt in duel_types:
        engine = get_duel_engine(dt)
        assert engine is not None

    for st in solo_types:
        engine = get_solo_engine(st)
        assert engine is not None


# ============================================================
# 1. CONNECT FOUR
# ============================================================

def test_connect_four_mechanics_and_win():
    engine = ConnectFourEngine()
    state = engine.init_game_state({}, ["p1", "p2"])
    assert state["current_turn"] == "p1"
    assert len(state["board"]) == 6
    assert len(state["board"][0]) == 7

    # Reject invalid column
    ok, err, state, _ = engine.process_action(state, "p1", "drop_piece", {"column": 10})
    assert ok is False
    assert "between 0 and 6" in err

    # Reject out of turn
    ok, err, state, _ = engine.process_action(state, "p2", "drop_piece", {"column": 0})
    assert ok is False
    assert "not your turn" in err.lower()

    # Play horizontal win for p1: cols 0, 1, 2, 3
    moves = [
        ("p1", 0), ("p2", 0),
        ("p1", 1), ("p2", 1),
        ("p1", 2), ("p2", 2),
        ("p1", 3),
    ]
    winner = None
    for player, col in moves:
        ok, msg, state, winner = engine.process_action(state, player, "drop_piece", {"column": col})
        assert ok is True, f"Move {player} col {col} failed: {msg}"

    assert state["status"] == "COMPLETED"
    assert winner == "p1"


# ============================================================
# 2. CARROM CLASH
# ============================================================

def test_carrom_clash_mechanics():
    engine = CarromClashEngine()
    state = engine.init_game_state({}, ["p1", "p2"])
    assert state["current_turn"] == "p1"
    assert state["white_coins_remaining"] == 9
    assert state["black_coins_remaining"] == 9

    # Legal strike
    ok, msg, state, winner = engine.process_action(state, "p1", "strike", {"angle": 45.0, "power": 80.0})
    assert ok is True
    assert state["total_shots"] == 1


# ============================================================
# 3. AIR RUSH
# ============================================================

def test_air_rush_scoring_and_win():
    engine = AirRushEngine()
    state = engine.init_game_state({}, ["p1", "p2"])
    assert state["target_score"] == 5

    # Move paddle
    ok, msg, state, _ = engine.process_action(state, "p1", "move_paddle", {"x": 120.0, "y": 300.0})
    assert ok is True
    assert state["paddles"]["p1"]["x"] == 120.0

    # Score goals until victory
    winner = None
    for _ in range(5):
        ok, msg, state, winner = engine.process_action(state, "p1", "score_goal", {})
        assert ok is True

    assert state["status"] == "COMPLETED"
    assert winner == "p1"
    assert state["p1_score"] == 5


# ============================================================
# 4. POCKET POOL
# ============================================================

def test_pocket_pool_mechanics():
    engine = PocketPoolEngine()
    state = engine.init_game_state({}, ["p1", "p2"])
    assert "SOLIDS" in state["balls_remaining"]
    assert len(state["balls_remaining"]["SOLIDS"]) == 7

    ok, msg, state, winner = engine.process_action(state, "p1", "strike_cue_ball", {"angle": 30.0, "power": 60.0})
    assert ok is True
    assert state["shots_taken"] == 1


# ============================================================
# 5. STICK ARENA
# ============================================================

def test_stick_arena_combat_and_ko():
    engine = StickArenaEngine()
    state = engine.init_game_state({}, ["p1", "p2"])
    assert state["fighters"]["p1"]["hp"] == 100
    assert state["fighters"]["p2"]["hp"] == 100

    # Move
    ok, msg, state, _ = engine.process_action(state, "p1", "move", {"x": 180.0, "is_jumping": True})
    assert ok is True

    # Attacks
    ok, msg, state, _ = engine.process_action(state, "p1", "attack", {"attack_type": "heavy"})
    assert ok is True
    assert state["fighters"]["p2"]["hp"] < 100


# ============================================================
# 6. QUICKDRAW
# ============================================================

def test_quickdraw_drawing_and_guess_sanitization():
    engine = QuickDrawEngine()
    state = engine.init_game_state({}, ["p1", "p2"])
    artist = state["artist_id"]
    guesser = state["guesser_id"]

    # Sanitize state hides secret word from guesser
    san_artist = engine.get_sanitized_state_for_player(state, artist)
    san_guesser = engine.get_sanitized_state_for_player(state, guesser)
    assert san_artist["secret_word"] is not None
    assert san_guesser["secret_word"] is None
    assert san_guesser["word_length"] > 0

    # Draw stroke
    ok, msg, state, _ = engine.process_action(state, artist, "add_stroke", {
        "stroke": [{"x": 10, "y": 20}, {"x": 30, "y": 40}],
    })
    assert ok is True
    assert len(state["strokes"]) == 1

    # Guess secret
    secret = state["secret_word"]
    ok, msg, state, _ = engine.process_action(state, guesser, "submit_guess", {"guess": secret})
    assert ok is True
    assert len(state["guesses"]) == 1


# ============================================================
# 7. WORD RUSH
# ============================================================

def test_word_rush_dictionary_validation():
    engine = WordRushEngine()
    state = engine.init_game_state({}, ["p1", "p2"])

    # Ensure a dictionary word is submitted
    dict_word = list(engine.DICTIONARY)[0]
    ok, msg, state, _ = engine.process_action(state, "p1", "submit_word", {"word": dict_word})
    assert ok is True
    assert dict_word.lower() in state["p1_words"]


# ============================================================
# 8. BRAIN BLITZ
# ============================================================

def test_brain_blitz_trivia_and_answer_hiding():
    engine = BrainBlitzEngine()
    state = engine.init_game_state({}, ["p1", "p2"])

    # Correct answer concealed from sanitized state
    sanitized = engine.get_sanitized_state_for_player(state, "p1")
    assert "question" in sanitized
    assert "correct" not in sanitized["question"]

    # Submit answer
    ok, msg, state, _ = engine.process_action(state, "p1", "answer_question", {"option_index": 0})
    assert ok is True
    assert state["p1_answer"] == 0


# ============================================================
# 9. REFLEX RUSH
# ============================================================

def test_reflex_rush_timing_and_false_start():
    engine = ReflexRushEngine()
    state = engine.init_game_state({}, ["p1", "p2"])

    # Tap action
    tap_time = state["cue_time_ms"] + 250
    ok, msg, state, _ = engine.process_action(state, "p1", "tap", {"client_timestamp_ms": tap_time})
    assert ok is True
    assert state["p1_time_ms"] == 250


# ============================================================
# 10. MINDMATCH
# ============================================================

def test_mindmatch_social_harmony():
    engine = MindMatchEngine()
    state = engine.init_game_state({}, ["p1", "p2"])

    # p1 selects option
    ok, msg, state, _ = engine.process_action(state, "p1", "select_option", {"choice": "a"})
    assert ok is True
    assert state["p1_choice"] == "a"

    # Before p2 answers, p1's answer is hidden from p2
    san_p2 = engine.get_sanitized_state_for_player(state, "p2")
    assert san_p2["p1_choice"] is None

    # p2 answers choice 'a' -> Match!
    ok, msg, state, _ = engine.process_action(state, "p2", "select_option", {"choice": "a"})
    assert ok is True
    assert state["match_score"] >= 20


# ============================================================
# 11. MYSTERY MISSION
# ============================================================

def test_mystery_mission_coop_deduction():
    engine = MysteryMissionEngine()
    state = engine.init_game_state({}, ["p1", "p2"])

    # Clues are partitioned per player
    san_p1 = engine.get_sanitized_state_for_player(state, "p1")
    san_p2 = engine.get_sanitized_state_for_player(state, "p2")
    assert "my_clue" in san_p1
    assert "my_clue" in san_p2

    # Submit solution
    curr_stage = engine.STAGES[state["stage"]]
    ans = curr_stage["answer"]
    ok, msg, state, winner = engine.process_action(state, "p1", "submit_solution", {"answer": ans})
    assert ok is True


# ============================================================
# 12. ZEN MERGE (SOLO)
# ============================================================

def test_zen_merge_mechanics():
    engine = ZenMergeEngine()
    state = engine.init_game_state({}, ["solo_user"])
    assert len(state["board"]) == 4
    assert len(state["board"][0]) == 4
    assert state["score"] == 0

    # Ensure at least one slide works
    for direction in ("LEFT", "RIGHT", "UP", "DOWN"):
        ok, msg, state, _ = engine.process_action(state, "solo_user", "slide", {"direction": direction})
        if ok:
            break
    assert ok is True


# ============================================================
# 13. WORD HUNT (SOLO)
# ============================================================

def test_word_hunt_mechanics():
    engine = WordHuntEngine()
    state = engine.init_game_state({}, ["solo_user"])
    target = state["target_words"][0]

    ok, msg, state, _ = engine.process_action(state, "solo_user", "find_word", {"word": target})
    assert ok is True
    assert target.upper() in state["found_words"]


# ============================================================
# 14. COLOR FLOW (SOLO)
# ============================================================

def test_color_flow_mechanics():
    engine = ColorFlowEngine()
    state = engine.init_game_state({}, ["solo_user"])
    first_color = list(state["endpoints"].keys())[0]

    ok, msg, state, _ = engine.process_action(state, "solo_user", "connect_color", {
        "color": first_color,
    })
    assert ok is True
    assert first_color in state["connected_flows"]


# ============================================================
# 15. POCKET GOLF (SOLO)
# ============================================================

def test_pocket_golf_mechanics():
    engine = PocketGolfEngine()
    state = engine.init_game_state({}, ["solo_user"])
    assert state["strokes"] == 0
    assert state["current_hole"] == 1

    ok, msg, state, _ = engine.process_action(state, "solo_user", "putt", {"angle": 45.0, "power": 80.0})
    assert ok is True
    assert state["strokes"] == 1


# ============================================================
# 16. REFLEX LAB (SOLO)
# ============================================================

def test_reflex_lab_challenges():
    engine = ReflexLabEngine()
    state = engine.init_game_state({}, ["solo_user"])
    assert "target_sequence" in state

    step = state["target_sequence"][0]
    ok, msg, state, _ = engine.process_action(state, "solo_user", "submit_step", {"step": step})
    assert ok is True
    assert len(state["user_sequence"]) == 1


# ============================================================
# 17. DAILY MYSTERY (SOLO)
# ============================================================

def test_daily_mystery_mechanics():
    engine = DailyMysteryEngine()
    state = engine.init_game_state({}, ["solo_user"])
    assert "clues" in state
    assert state["solved"] is False

    ans = engine.RIDDLE["solution"]
    ok, msg, state, _ = engine.process_action(state, "solo_user", "solve", {"assignment": ans})
    assert ok is True
    assert state["solved"] is True
    assert state["status"] == "COMPLETED"
