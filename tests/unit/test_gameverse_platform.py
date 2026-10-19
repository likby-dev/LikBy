"""
tests.unit.test_gameverse_platform
Comprehensive unit tests for the LikBy GameVerse ecosystem:
- Matchmaking Queue Service (join, cancel, pairing, state lifecycle)
- Progression & Achievements Service (XP leveling, achievements unlocking, leaderboard)
- Puzzle Generator Service (Word Hunt, Color Flow, Pocket Golf, Daily Mystery)
- GameVerse REST API endpoints in play.py
"""

import asyncio
import pytest
from starlette.testclient import TestClient

from likby.domain.entities.user import User
from likby.domain.enums import GameType
from likby.main import app
from likby.services.game_matchmaking_service import MatchQueueState
from likby.services.progression_service import ProgressionService
from likby.services.puzzle_generator_service import PuzzleGeneratorService


# ==============================================================================
# 1. Progression & Leveling Service Unit Tests (Standalone)
# ==============================================================================
def test_progression_level_curve_and_xp():
    svc = ProgressionService()

    # Initial state
    p = svc.get_or_create_progression("user_prog_test_1")
    assert p.level == 1
    assert p.total_xp == 0
    assert p.current_streak == 0

    # 1. Award victory XP in duel
    prog, unlocked = svc.record_duel_completion(
        user_id="user_prog_test_1",
        game_id=GameType.CONNECT_FOUR,
        is_winner=True,
        is_draw=False,
    )
    assert prog.total_xp >= 150
    assert prog.total_duels_won == 1
    assert prog.current_streak == 1

    # Check achievements unlocked: first_victory
    unlocked_ids = [a.id for a in unlocked]
    assert "first_victory" in unlocked_ids

    # 2. Win 2 more times to trigger streak_master (streak >= 3)
    svc.record_duel_completion("user_prog_test_1", GameType.CONNECT_FOUR, is_winner=True)
    prog3, unlocked3 = svc.record_duel_completion("user_prog_test_1", GameType.CONNECT_FOUR, is_winner=True)
    assert prog3.current_streak == 3
    unlocked_ids3 = [a.id for a in unlocked3]
    assert "streak_master" in unlocked_ids3

    # Level up threshold: Level 1 -> Level 2 requires 200 XP
    assert prog3.level >= 2

    # Check overview schema
    overview = svc.get_user_overview("user_prog_test_1")
    assert overview["level"] >= 2
    assert overview["current_streak"] == 3
    assert overview["achievements_count"] >= 2


def test_progression_leaderboard():
    svc = ProgressionService()

    # Seed completions
    svc.record_duel_completion("champ_top_1", GameType.CARROM_CLASH, is_winner=True)
    svc.record_duel_completion("champ_top_1", GameType.CARROM_CLASH, is_winner=True)
    svc.record_duel_completion("champ_top_2", GameType.CARROM_CLASH, is_winner=True)

    lb = svc.get_leaderboard(limit=10)
    assert len(lb) >= 2
    assert lb[0]["rank"] == 1
    assert lb[0]["total_xp"] >= lb[1]["total_xp"]


# ==============================================================================
# 2. Puzzle Generator Service Unit Tests (Standalone)
# ==============================================================================
def test_puzzle_generator_word_hunt():
    svc = PuzzleGeneratorService()
    puzzle = svc.generate_word_hunt_puzzle(grid_size=5, category="TECH", seed=4242)

    assert puzzle["grid_size"] == 5
    assert len(puzzle["grid"]) == 5
    for row in puzzle["grid"]:
        assert len(row) == 5

    assert len(puzzle["words"]) > 0
    # Determinism: same seed generates same grid
    puzzle2 = svc.generate_word_hunt_puzzle(grid_size=5, category="TECH", seed=4242)
    assert puzzle["grid"] == puzzle2["grid"]
    assert puzzle["words"] == puzzle2["words"]


def test_puzzle_generator_color_flow():
    svc = PuzzleGeneratorService()
    cf = svc.generate_color_flow_puzzle(grid_size=4, flow_count=3, seed=888)

    assert cf["grid_size"] == 4
    assert len(cf["endpoints"]) == 3
    for ep in cf["endpoints"]:
        assert "color" in ep
        assert len(ep["start"]) == 2
        assert len(ep["end"]) == 2
        assert ep["start"] != ep["end"]


def test_daily_mystery_deterministic_verification():
    svc = PuzzleGeneratorService()
    riddle = svc.get_canonical_daily_challenge("2026-10-19")
    assert "clue" in riddle
    assert "hint" in riddle

    # Solution verification
    ok, expl = svc.verify_daily_mystery_solution("2026-10-19", "echo")
    assert isinstance(ok, bool)
    assert isinstance(expl, str)


# ==============================================================================
# 3. Matchmaking Service Tests (With TestClient Lifespan)
# ==============================================================================
def test_matchmaking_enqueue_and_cancellation():
    with TestClient(app) as client:
        svc = app.state.game_matchmaking_service
        user_repo = app.state.user_repo

        # Seed test user
        u1 = User(id="user_mm_p1", telegram_id=11002233)
        asyncio.run(user_repo.save(u1))

        # 1. Player 1 joins queue
        success, msg, entry = asyncio.run(svc.enqueue_player(user_id="user_mm_p1", game_type=GameType.CONNECT_FOUR))
        assert success is True
        assert entry is not None
        assert entry.state == MatchQueueState.QUEUED

        # Status check
        status1 = svc.get_status("user_mm_p1")
        assert status1["state"] == MatchQueueState.QUEUED.value
        assert status1["game_id"] == GameType.CONNECT_FOUR.value

        # 2. Player 1 cancels search
        cancelled = asyncio.run(svc.cancel_player("user_mm_p1"))
        assert cancelled is True

        status_after_cancel = svc.get_status("user_mm_p1")
        assert status_after_cancel["state"] == MatchQueueState.DISCONNECTED.value


def test_matchmaking_pairing():
    with TestClient(app) as client:
        svc = app.state.game_matchmaking_service
        user_repo = app.state.user_repo

        # Seed test players
        u_a = User(id="user_pair_a", telegram_id=33445566)
        u_b = User(id="user_pair_b", telegram_id=77889900)
        asyncio.run(user_repo.save(u_a))
        asyncio.run(user_repo.save(u_b))

        # 1. Player A enqueues
        s_a, m_a, e_a = asyncio.run(svc.enqueue_player(user_id="user_pair_a", game_type=GameType.CARROM_CLASH))
        assert s_a is True
        assert e_a.state == MatchQueueState.QUEUED

        # 2. Player B enqueues for the same game
        s_b, m_b, e_b = asyncio.run(svc.enqueue_player(user_id="user_pair_b", game_type=GameType.CARROM_CLASH))
        assert s_b is True
        assert "Match found" in m_b

        # 3. Status checks
        status_a = svc.get_status("user_pair_a")
        status_b = svc.get_status("user_pair_b")

        assert status_a["state"] == MatchQueueState.MATCHED.value
        assert status_b["state"] == MatchQueueState.MATCHED.value
        assert status_a["partner_id"] == "user_pair_b"
        assert status_b["partner_id"] == "user_pair_a"
        assert status_a["session_id"] == status_b["session_id"]


# ==============================================================================
# 4. GameVerse REST API Endpoints Tests
# ==============================================================================
def test_gameverse_api_endpoints():
    with TestClient(app) as client:
        # Seed test user
        user_repo = app.state.user_repo
        test_user = User(id="user_gameverse_api_test", telegram_id=55443322)
        asyncio.run(user_repo.save(test_user))
        headers = {"X-User-Id": "user_gameverse_api_test"}

        # 1. Progression & Entitlements
        res_prog = client.get("/api/v1/play/progression", headers=headers)
        assert res_prog.status_code == 200
        data_prog = res_prog.json()
        assert "level" in data_prog
        assert "total_xp" in data_prog

        # 2. Achievements Catalog
        res_ach = client.get("/api/v1/play/achievements", headers=headers)
        assert res_ach.status_code == 200
        data_ach = res_ach.json()
        assert isinstance(data_ach, list)
        assert len(data_ach) >= 10

        # 3. Leaderboard
        res_lb = client.get("/api/v1/play/leaderboard?limit=5", headers=headers)
        assert res_lb.status_code == 200
        data_lb = res_lb.json()
        assert isinstance(data_lb, list)

        # 4. Canonical Daily Challenge
        res_daily = client.get("/api/v1/play/daily_challenge", headers=headers)
        assert res_daily.status_code == 200
        data_daily = res_daily.json()
        assert "clue" in data_daily
        assert "hint" in data_daily
        assert "answer_key" not in data_daily  # Hidden security rule!

        # 5. Solo Generators
        res_wh = client.get("/api/v1/play/solo/word_hunt/generate?grid_size=5&category=TECH", headers=headers)
        assert res_wh.status_code == 200
        wh_data = res_wh.json()
        assert "grid" in wh_data

        res_cf = client.get("/api/v1/play/solo/color_flow/generate?grid_size=4&flow_count=3", headers=headers)
        assert res_cf.status_code == 200
        cf_data = res_cf.json()
        assert "endpoints" in cf_data

        # 6. Matchmaking lifecycle via API
        res_join = client.post(
            "/api/v1/play/matchmaking/join",
            json={"game_id": "connect_four", "mode": "casual"},
            headers=headers,
        )
        assert res_join.status_code == 200
        join_data = res_join.json()
        assert join_data["status"] == "success"
        assert join_data["queue"]["state"] in ["QUEUED", "MATCHED"]

        res_status = client.get("/api/v1/play/matchmaking/status", headers=headers)
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert "state" in status_data

        res_leave = client.post("/api/v1/play/matchmaking/leave", headers=headers)
        assert res_leave.status_code == 200
        leave_data = res_leave.json()
        assert leave_data["status"] == "success"
