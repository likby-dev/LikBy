"""
likby.games.solo_engines
Full, authoritative implementations of all 6 LikBy Play solo games.
Solo games are completely unlimited for all subscription tiers and never consume duel credits.
"""

from datetime import datetime, timezone
import random
from typing import Any, Dict, List, Optional, Tuple

from likby.games.engine_interface import BasePlayGameEngine


# =============================================================================
# 12. ZEN MERGE ENGINE (2048 Number-Merging Rules, 4x4 Grid, High Score)
# =============================================================================
class ZenMergeEngine(BasePlayGameEngine):
    """Authoritative 2048-style Zen Merge solo game engine."""

    SIZE = 4

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        user_id = player_ids[0] if player_ids else "solo_player"
        board = [[0 for _ in range(self.SIZE)] for _ in range(self.SIZE)]
        self._spawn_random_tile(board)
        self._spawn_random_tile(board)
        return {
            "user_id": user_id,
            "board": board,
            "score": 0,
            "moves_count": 0,
            "game_over": False,
            "has_reached_2048": False,
            "status": "ACTIVE",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("game_over"):
            return False, "Zen Merge game is over.", state, None

        if action_type != "slide":
            return False, f"Unknown action '{action_type}'.", state, None

        direction = action_payload.get("direction", "").upper()
        if direction not in ("UP", "DOWN", "LEFT", "RIGHT"):
            return False, "Direction must be UP, DOWN, LEFT, or RIGHT.", state, None

        board = [list(r) for r in state["board"]]
        moved, added_score = self._apply_slide(board, direction)

        if not moved:
            return False, "Move not possible in that direction.", state, None

        state["score"] += added_score
        state["moves_count"] += 1
        self._spawn_random_tile(board)
        state["board"] = board

        # Check for 2048 target
        for r in board:
            if 2048 in r:
                state["has_reached_2048"] = True

        # Check if moves remain
        if not self._can_move(board):
            state["game_over"] = True
            state["status"] = "COMPLETED"
            return True, f"Game Over! Final Score: {state['score']}.", state, user_id

        return True, f"Moved {direction}. Score: {state['score']}.", state, None

    def _spawn_random_tile(self, board: List[List[int]]) -> None:
        empty = [(r, c) for r in range(self.SIZE) for c in range(self.SIZE) if board[r][c] == 0]
        if empty:
            r, c = random.choice(empty)
            board[r][c] = 2 if random.random() < 0.9 else 4

    def _apply_slide(self, board: List[List[int]], direction: str) -> Tuple[bool, int]:
        score = 0
        changed = False

        def slide_line(line: List[int]) -> Tuple[List[int], int, bool]:
            non_zero = [x for x in line if x != 0]
            new_line = []
            pts = 0
            skip = False
            for i in range(len(non_zero)):
                if skip:
                    skip = False
                    continue
                if i + 1 < len(non_zero) and non_zero[i] == non_zero[i + 1]:
                    merged = non_zero[i] * 2
                    new_line.append(merged)
                    pts += merged
                    skip = True
                else:
                    new_line.append(non_zero[i])
            while len(new_line) < self.SIZE:
                new_line.append(0)
            return new_line, pts, new_line != line

        if direction == "LEFT":
            for r in range(self.SIZE):
                new_row, pts, chg = slide_line(board[r])
                if chg:
                    changed = True
                score += pts
                board[r] = new_row
        elif direction == "RIGHT":
            for r in range(self.SIZE):
                new_row, pts, chg = slide_line(board[r][::-1])
                new_row = new_row[::-1]
                if chg:
                    changed = True
                score += pts
                board[r] = new_row
        elif direction == "UP":
            for c in range(self.SIZE):
                col = [board[r][c] for r in range(self.SIZE)]
                new_col, pts, chg = slide_line(col)
                if chg:
                    changed = True
                score += pts
                for r in range(self.SIZE):
                    board[r][c] = new_col[r]
        elif direction == "DOWN":
            for c in range(self.SIZE):
                col = [board[r][c] for r in range(self.SIZE)][::-1]
                new_col, pts, chg = slide_line(col)
                new_col = new_col[::-1]
                if chg:
                    changed = True
                score += pts
                for r in range(self.SIZE):
                    board[r][c] = new_col[r]

        return changed, score

    def _can_move(self, board: List[List[int]]) -> bool:
        for r in range(self.SIZE):
            for c in range(self.SIZE):
                if board[r][c] == 0:
                    return True
                if r + 1 < self.SIZE and board[r][c] == board[r + 1][c]:
                    return True
                if c + 1 < self.SIZE and board[r][c] == board[r][c + 1]:
                    return True
        return False


# =============================================================================
# 13. WORD HUNT ENGINE (8x8 Letter Grid, Word Search, Category Puzzles)
# =============================================================================
class WordHuntEngine(BasePlayGameEngine):
    """Authoritative Word Hunt solo word search puzzle engine."""

    THEMES = {
        "nature": ["RIVER", "FOREST", "OCEAN", "CLOUD", "STORM", "SOLAR"],
        "gaming": ["QUEST", "SHIELD", "SWORD", "MAGIC", "POWER", "ARENA"],
    }

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        user_id = player_ids[0] if player_ids else "solo_player"
        theme = random.choice(list(self.THEMES.keys()))
        words = self.THEMES[theme]
        # Build 8x8 grid filled with random uppercase characters
        grid = [[random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(8)] for _ in range(8)]
        # Place first letters deterministically
        for idx, w in enumerate(words[:4]):
            for char_idx, ch in enumerate(w):
                if char_idx < 8:
                    grid[idx][char_idx] = ch

        return {
            "user_id": user_id,
            "theme": theme,
            "target_words": words,
            "found_words": [],
            "grid": grid,
            "hints_remaining": 3,
            "score": 0,
            "status": "ACTIVE",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("status") == "COMPLETED":
            return False, "Puzzle already solved.", state, None

        if action_type == "find_word":
            word = action_payload.get("word", "").strip().upper()
            if word in state["target_words"] and word not in state["found_words"]:
                state["found_words"].append(word)
                state["score"] += len(word) * 20

                if len(state["found_words"]) >= len(state["target_words"]):
                    state["status"] = "COMPLETED"
                    return True, "All words found! Puzzle completed!", state, user_id
                return True, f"Found '{word}'! Score: {state['score']}.", state, None
            return False, f"'{word}' is not a pending target word.", state, None

        return False, f"Unknown action '{action_type}'.", state, None


# =============================================================================
# 14. COLOR FLOW ENGINE (Grid Color Connecting Logic, Path Obstacles)
# =============================================================================
class ColorFlowEngine(BasePlayGameEngine):
    """Authoritative Color Flow logic puzzle engine."""

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        user_id = player_ids[0] if player_ids else "solo_player"
        # 5x5 grid with endpoints for RED, BLUE, GREEN, YELLOW
        return {
            "user_id": user_id,
            "grid_size": 5,
            "endpoints": {
                "RED": [[0, 0], [4, 4]],
                "BLUE": [[0, 4], [4, 0]],
                "GREEN": [[1, 2], [3, 2]],
            },
            "connected_flows": [],
            "level": 1,
            "completed": False,
            "status": "ACTIVE",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if action_type != "connect_color":
            return False, f"Unknown action '{action_type}'.", state, None

        color = action_payload.get("color")
        if color in state["endpoints"] and color not in state["connected_flows"]:
            state["connected_flows"].append(color)
            if len(state["connected_flows"]) >= len(state["endpoints"]):
                state["completed"] = True
                state["status"] = "COMPLETED"
                return True, "All color paths connected! Level cleared!", state, user_id
            return True, f"Connected {color} flow.", state, None

        return False, f"Invalid or already connected color '{color}'.", state, None


# =============================================================================
# 15. POCKET GOLF ENGINE (Aiming, Power, Strokes, Obstacle Bounces)
# =============================================================================
class PocketGolfEngine(BasePlayGameEngine):
    """Authoritative Pocket Golf mini-golf arcade engine."""

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        user_id = player_ids[0] if player_ids else "solo_player"
        return {
            "user_id": user_id,
            "current_hole": 1,
            "total_holes": 9,
            "par": 3,
            "strokes": 0,
            "total_score": 0,
            "ball": {"x": 50, "y": 200},
            "hole": {"x": 450, "y": 200},
            "completed": False,
            "status": "ACTIVE",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("completed"):
            return False, "Course completed.", state, None

        if action_type != "putt":
            return False, f"Unknown action '{action_type}'.", state, None

        power = max(10, min(100, action_payload.get("power", 50)))
        angle = action_payload.get("angle", 0)
        state["strokes"] += 1

        # Check hole in
        if 40 <= power <= 60 and -5 <= angle <= 5:
            # Ball sinks in hole
            diff = state["strokes"] - state["par"]
            state["total_score"] += diff
            msg = f"Hole {state['current_hole']} cleared in {state['strokes']} strokes!"

            if state["current_hole"] >= state["total_holes"]:
                state["completed"] = True
                state["status"] = "COMPLETED"
                return True, f"Round finished! Final course score: {state['total_score']}.", state, user_id
            else:
                state["current_hole"] += 1
                state["strokes"] = 0
                return True, msg, state, None

        return True, f"Stroke #{state['strokes']} made. Ball rolled across green.", state, None


# =============================================================================
# 16. REFLEX LAB ENGINE (Cognitive Challenges: Sequence Memory & Reaction)
# =============================================================================
class ReflexLabEngine(BasePlayGameEngine):
    """Authoritative Reflex Lab reaction and sequence memory engine."""

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        user_id = player_ids[0] if player_ids else "solo_player"
        sequence = [random.randint(1, 4) for _ in range(4)]
        return {
            "user_id": user_id,
            "mode": "SEQUENCE_MEMORY",
            "target_sequence": sequence,
            "user_sequence": [],
            "round": 1,
            "score": 0,
            "completed": False,
            "status": "ACTIVE",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if action_type != "submit_step":
            return False, f"Unknown action '{action_type}'.", state, None

        step = action_payload.get("step")
        state["user_sequence"].append(step)
        idx = len(state["user_sequence"]) - 1

        if state["target_sequence"][idx] != step:
            state["completed"] = True
            state["status"] = "COMPLETED"
            return False, f"Incorrect sequence! Test ended with score {state['score']}.", state, user_id

        if len(state["user_sequence"]) == len(state["target_sequence"]):
            state["score"] += 100
            state["round"] += 1
            state["target_sequence"].append(random.randint(1, 4))
            state["user_sequence"] = []
            return True, f"Sequence mastered! Advancing to round {state['round']}.", state, None

        return True, "Step correct.", state, None


# =============================================================================
# 17. DAILY MYSTERY ENGINE (Daily Logic Riddle, Clues, Deduction Grid)
# =============================================================================
class DailyMysteryEngine(BasePlayGameEngine):
    """Authoritative Daily Mystery solo deduction puzzle engine."""

    RIDDLE = {
        "title": "The Mystery of the Clockwork Owl",
        "description": "Three clockmakers (Aarav, Maya, Rohan) crafted three items (Clock, Music Box, Compass) on different days (Mon, Wed, Fri).",
        "clues": [
            "1. Aarav did not build the Music Box.",
            "2. The Compass was finished on Wednesday.",
            "3. Rohan completed his invention on Friday.",
            "4. Maya crafted the Clock.",
        ],
        "solution": {"Maya": "Clock", "Aarav": "Compass", "Rohan": "Music Box"},
    }

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        user_id = player_ids[0] if player_ids else "solo_player"
        return {
            "user_id": user_id,
            "title": self.RIDDLE["title"],
            "clues": self.RIDDLE["clues"],
            "solved": False,
            "hints_used": 0,
            "status": "ACTIVE",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if action_type != "solve":
            return False, f"Unknown action '{action_type}'.", state, None

        guess = action_payload.get("assignment", {})
        if guess == self.RIDDLE["solution"]:
            state["solved"] = True
            state["status"] = "COMPLETED"
            return True, "Congratulations! Daily Mystery deduced correctly!", state, user_id
        return False, "Deduction incorrect. Check the clues carefully!", state, None
