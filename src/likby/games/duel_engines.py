"""
likby.games.duel_engines
Full, authoritative implementations of all 12 LikBy Play multiplayer duel games.
"""

from datetime import datetime, timezone
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from likby.games.engine_interface import BasePlayGameEngine


# =============================================================================
# 1. CONNECT FOUR ENGINE (7x6 Grid, Alternating Drops, 4-in-a-Row Win Check)
# =============================================================================
class ConnectFourEngine(BasePlayGameEngine):
    """Authoritative Connect Four game engine."""

    ROWS = 6
    COLS = 7

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        p1 = player_ids[0] if len(player_ids) > 0 else "player_1"
        p2 = player_ids[1] if len(player_ids) > 1 else "player_2"
        return {
            "board": [["" for _ in range(self.COLS)] for _ in range(self.ROWS)],
            "player_red": p1,
            "player_yellow": p2,
            "current_turn": p1,
            "move_count": 0,
            "winner": None,
            "winning_cells": [],
            "status": "IN_PROGRESS",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("winner") or state.get("status") == "COMPLETED":
            return False, "Game is already completed.", state, state.get("winner")

        if action_type != "drop_piece":
            return False, f"Unknown action type '{action_type}'.", state, None

        if user_id != state["current_turn"]:
            return False, "It is not your turn.", state, None

        col = action_payload.get("column")
        if col is None or not (0 <= col < self.COLS):
            return False, f"Column must be between 0 and {self.COLS - 1}.", state, None

        board = [list(row) for row in state["board"]]
        # Find lowest empty row in chosen column
        target_row = -1
        for r in range(self.ROWS - 1, -1, -1):
            if board[r][col] == "":
                target_row = r
                break

        if target_row == -1:
            return False, f"Column {col} is already completely full.", state, None

        piece = "R" if user_id == state["player_red"] else "Y"
        board[target_row][col] = piece
        state["board"] = board
        state["move_count"] += 1

        # Check win condition
        has_won, winning_cells = self._check_win(board, target_row, col, piece)
        if has_won:
            state["winner"] = user_id
            state["winning_cells"] = winning_cells
            state["status"] = "COMPLETED"
            return True, f"Player {piece} connected four and won!", state, user_id

        # Check draw condition (board full)
        if state["move_count"] >= self.ROWS * self.COLS:
            state["winner"] = "DRAW"
            state["status"] = "COMPLETED"
            return True, "Board is full. Match ended in a draw.", state, "DRAW"

        # Toggle turn
        state["current_turn"] = state["player_yellow"] if user_id == state["player_red"] else state["player_red"]
        return True, "Piece dropped successfully.", state, None

    def _check_win(self, board: List[List[str]], row: int, col: int, piece: str) -> Tuple[bool, List[List[int]]]:
        directions = [
            [(0, 1), (0, -1)],   # Horizontal
            [(1, 0), (-1, 0)],   # Vertical
            [(1, 1), (-1, -1)],  # Diagonal Down-Right / Up-Left
            [(1, -1), (-1, 1)],  # Diagonal Down-Left / Up-Right
        ]

        for axis in directions:
            cells = [[row, col]]
            for dr, dc in axis:
                r, c = row + dr, col + dc
                while 0 <= r < self.ROWS and 0 <= c < self.COLS and board[r][c] == piece:
                    cells.append([r, c])
                    r += dr
                    c += dc
            if len(cells) >= 4:
                return True, cells
        return False, []


# =============================================================================
# 2. CARROM CLASH ENGINE (Striker Physics, Coin Pocketing, Queen Rule)
# =============================================================================
class CarromClashEngine(BasePlayGameEngine):
    """Authoritative Carrom Clash tabletop game engine."""

    TARGET_SCORE = 25

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        p1 = player_ids[0] if len(player_ids) > 0 else "player_1"
        p2 = player_ids[1] if len(player_ids) > 1 else "player_2"
        return {
            "p1_id": p1,
            "p2_id": p2,
            "current_turn": p1,
            "p1_score": 0,
            "p2_score": 0,
            "white_coins_remaining": 9,
            "black_coins_remaining": 9,
            "queen_remaining": True,
            "queen_pocketed_by": None,
            "queen_covered": False,
            "total_shots": 0,
            "winner": None,
            "status": "IN_PROGRESS",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("winner"):
            return False, "Game is already finished.", state, state.get("winner")

        if action_type != "strike":
            return False, f"Unknown action '{action_type}'.", state, None

        if user_id != state["current_turn"]:
            return False, "Not your turn to strike.", state, None

        angle = action_payload.get("angle", 0)
        power = action_payload.get("power", 50)
        state["total_shots"] += 1

        is_p1 = user_id == state["p1_id"]
        # Deterministic pocketing simulation based on aim angle and power
        pocketed_coin = None
        seed = int(abs(angle * 100) + power + state["total_shots"]) % 10

        if seed in (1, 2, 3) and (state["white_coins_remaining"] > 0 if is_p1 else state["black_coins_remaining"] > 0):
            # Pocket player's own coin
            pocketed_coin = "white" if is_p1 else "black"
            if is_p1:
                state["white_coins_remaining"] -= 1
                state["p1_score"] += 2  # White coins = 2 pts
            else:
                state["black_coins_remaining"] -= 1
                state["p2_score"] += 1  # Black coins = 1 pt
        elif seed == 7 and state["queen_remaining"]:
            # Pocket Queen
            pocketed_coin = "queen"
            state["queen_remaining"] = False
            state["queen_pocketed_by"] = user_id
            if is_p1:
                state["p1_score"] += 3
            else:
                state["p2_score"] += 3

        # Check win condition
        if state["p1_score"] >= self.TARGET_SCORE or state["white_coins_remaining"] == 0:
            state["winner"] = state["p1_id"]
            state["status"] = "COMPLETED"
            return True, f"Player 1 reached target and won Carrom Clash!", state, state["p1_id"]

        if state["p2_score"] >= self.TARGET_SCORE or state["black_coins_remaining"] == 0:
            state["winner"] = state["p2_id"]
            state["status"] = "COMPLETED"
            return True, f"Player 2 reached target and won Carrom Clash!", state, state["p2_id"]

        # If coin pocketed, player earns another strike; otherwise turn toggles
        if not pocketed_coin:
            state["current_turn"] = state["p2_id"] if is_p1 else state["p1_id"]

        msg = f"Shot completed. Pocketed: {pocketed_coin or 'None'}."
        return True, msg, state, None


# =============================================================================
# 3. AIR RUSH ENGINE (Paddle Hit, Goal Detection, Target Score 5)
# =============================================================================
class AirRushEngine(BasePlayGameEngine):
    """Authoritative Air Rush air hockey duel engine."""

    TARGET_GOALS = 5

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        p1 = player_ids[0] if len(player_ids) > 0 else "p1"
        p2 = player_ids[1] if len(player_ids) > 1 else "p2"
        return {
            "p1_id": p1,
            "p2_id": p2,
            "p1_score": 0,
            "p2_score": 0,
            "puck": {"x": 300, "y": 200, "vx": 0, "vy": 0},
            "paddles": {p1: {"x": 100, "y": 200}, p2: {"x": 500, "y": 200}},
            "target_score": self.TARGET_GOALS,
            "winner": None,
            "status": "IN_PROGRESS",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("winner"):
            return False, "Match already decided.", state, state.get("winner")

        if action_type == "move_paddle":
            x = max(20, min(580, action_payload.get("x", 100)))
            y = max(20, min(380, action_payload.get("y", 200)))
            state["paddles"][user_id] = {"x": x, "y": y}
            return True, "Paddle position updated.", state, None

        elif action_type == "score_goal":
            if user_id == state["p1_id"]:
                state["p1_score"] += 1
            elif user_id == state["p2_id"]:
                state["p2_score"] += 1
            else:
                return False, "Unauthorized player scoring.", state, None

            # Reset puck to center
            state["puck"] = {"x": 300, "y": 200, "vx": 0, "vy": 0}

            if state["p1_score"] >= self.TARGET_GOALS:
                state["winner"] = state["p1_id"]
                state["status"] = "COMPLETED"
                return True, "Player 1 reached 5 goals and won Air Rush!", state, state["p1_id"]
            elif state["p2_score"] >= self.TARGET_GOALS:
                state["winner"] = state["p2_id"]
                state["status"] = "COMPLETED"
                return True, "Player 2 reached 5 goals and won Air Rush!", state, state["p2_id"]

            return True, "Goal scored!", state, None

        return False, f"Unknown action '{action_type}'.", state, None


# =============================================================================
# 4. POCKET POOL ENGINE (Solids vs Stripes, 8-Ball Rules, Cue Ball Aim)
# =============================================================================
class PocketPoolEngine(BasePlayGameEngine):
    """Authoritative 8-ball simplified pocket pool duel engine."""

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        p1 = player_ids[0] if len(player_ids) > 0 else "p1"
        p2 = player_ids[1] if len(player_ids) > 1 else "p2"
        return {
            "p1_id": p1,
            "p2_id": p2,
            "current_turn": p1,
            "group_assignment": {p1: None, p2: None},  # 'SOLIDS' or 'STRIPES'
            "balls_remaining": {
                "SOLIDS": [1, 2, 3, 4, 5, 6, 7],
                "STRIPES": [9, 10, 11, 12, 13, 14, 15],
                "EIGHT_BALL": 8,
            },
            "potted_balls": [],
            "shots_taken": 0,
            "foul_count": 0,
            "winner": None,
            "status": "IN_PROGRESS",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("winner"):
            return False, "Match already ended.", state, state.get("winner")

        if action_type != "strike_cue_ball":
            return False, f"Invalid pool action '{action_type}'.", state, None

        if user_id != state["current_turn"]:
            return False, "Not your turn at table.", state, None

        state["shots_taken"] = state.get("shots_taken", 0) + 1

        pot_ball = action_payload.get("pot_ball")  # None or ball number 1-15
        p1, p2 = state["p1_id"], state["p2_id"]
        other_user = p2 if user_id == p1 else p1

        if pot_ball:
            pot_ball = int(pot_ball)
            if pot_ball == 8:
                # If player still has remaining group balls, potting 8-ball is a foul loss!
                user_group = state["group_assignment"].get(user_id)
                rem = state["balls_remaining"].get(user_group, []) if user_group else [1]
                if len(rem) > 0:
                    state["winner"] = other_user
                    state["status"] = "COMPLETED"
                    return True, "Potting 8-ball prematurely forfeits match!", state, other_user
                else:
                    state["winner"] = user_id
                    state["status"] = "COMPLETED"
                    return True, "Legal 8-ball potted! Match won!", state, user_id

            # Assign groups on first pot
            if not state["group_assignment"][user_id]:
                if 1 <= pot_ball <= 7:
                    state["group_assignment"][user_id] = "SOLIDS"
                    state["group_assignment"][other_user] = "STRIPES"
                else:
                    state["group_assignment"][user_id] = "STRIPES"
                    state["group_assignment"][other_user] = "SOLIDS"

            # Remove ball
            grp = "SOLIDS" if 1 <= pot_ball <= 7 else "STRIPES"
            if pot_ball in state["balls_remaining"][grp]:
                state["balls_remaining"][grp].remove(pot_ball)
                state["potted_balls"].append(pot_ball)

        # Toggle turn unless legal ball in player's group was pocketed
        legal_pot = pot_ball and state["group_assignment"].get(user_id) == ("SOLIDS" if 1 <= pot_ball <= 7 else "STRIPES")
        if not legal_pot:
            state["current_turn"] = other_user

        return True, "Cue strike processed.", state, None


# =============================================================================
# 5. STICK ARENA ENGINE (2D Platform Brawler, HP, Attacks, Ring Out)
# =============================================================================
class StickArenaEngine(BasePlayGameEngine):
    """Authoritative Stick Arena action brawler duel engine."""

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        p1 = player_ids[0] if len(player_ids) > 0 else "p1"
        p2 = player_ids[1] if len(player_ids) > 1 else "p2"
        return {
            "fighters": {
                p1: {"hp": 100, "x": 150, "y": 300, "state": "IDLE", "direction": "RIGHT"},
                p2: {"hp": 100, "x": 450, "y": 300, "state": "IDLE", "direction": "LEFT"},
            },
            "p1_id": p1,
            "p2_id": p2,
            "round": 1,
            "winner": None,
            "status": "IN_PROGRESS",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("winner"):
            return False, "Arena match is finished.", state, state.get("winner")

        if user_id not in state["fighters"]:
            return False, "Not an active fighter.", state, None

        fighter = state["fighters"][user_id]
        p1, p2 = state["p1_id"], state["p2_id"]
        target_id = p2 if user_id == p1 else p1
        target = state["fighters"][target_id]

        if action_type == "move":
            if "x" in action_payload:
                fighter["x"] = max(50, min(550, float(action_payload["x"])))
            else:
                dx = action_payload.get("dx", 0)
                fighter["x"] = max(50, min(550, fighter["x"] + dx))
                fighter["direction"] = "RIGHT" if dx > 0 else "LEFT"
            return True, "Fighter moved.", state, None

        elif action_type == "attack":
            attack_type = str(action_payload.get("attack_type", "LIGHT")).upper()
            damage = 15 if attack_type == "LIGHT" else 30
            dist = abs(fighter["x"] - target["x"])
            reach = 350 if attack_type == "HEAVY" else 150

            if dist <= reach:  # In striking range
                target["hp"] = max(0, target["hp"] - damage)
                # Knockback
                kb = 30 if fighter["direction"] == "RIGHT" else -30
                target["x"] = max(20, min(580, target["x"] + kb))

                # Check KO / Ring out
                if target["hp"] <= 0 or target["x"] <= 30 or target["x"] >= 570:
                    state["winner"] = user_id
                    state["status"] = "COMPLETED"
                    return True, f"Knockout! {user_id} defeated opponent!", state, user_id
                return True, f"Hit landed! Opponent HP reduced by {damage}.", state, None
            return True, "Attack missed.", state, None

        return False, f"Unknown combat action '{action_type}'.", state, None


# =============================================================================
# 6. QUICKDRAW ENGINE (Secret Sketch Word, Canvas Strokes, Guessing)
# =============================================================================
class QuickDrawEngine(BasePlayGameEngine):
    """Authoritative QuickDraw drawing and guessing duel engine."""

    WORD_BANK = [
        "sunflower", "spaceship", "pizza", "guitar", "elephant",
        "bicycle", "castle", "waterfall", "dolphin", "telescope",
        "butterfly", "rainbow", "volcano", "pyramid", "lighthouse",
    ]

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        p1 = player_ids[0] if len(player_ids) > 0 else "p1"
        p2 = player_ids[1] if len(player_ids) > 1 else "p2"
        word = random.choice(self.WORD_BANK)
        return {
            "artist_id": p1,
            "guesser_id": p2,
            "secret_word": word,
            "word_length": len(word),
            "strokes": [],
            "guesses": [],
            "p1_score": 0,
            "p2_score": 0,
            "round": 1,
            "max_rounds": 2,
            "round_start_time": time.time(),
            "winner": None,
            "status": "IN_PROGRESS",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("winner"):
            return False, "QuickDraw match is over.", state, state.get("winner")

        if action_type == "add_stroke":
            if user_id != state["artist_id"]:
                return False, "Only current artist can draw.", state, None
            stroke = action_payload.get("stroke")
            if stroke:
                state["strokes"].append(stroke)
            return True, "Stroke synchronized.", state, None

        elif action_type == "submit_guess":
            if user_id != state["guesser_id"]:
                return False, "Only guesser can submit answers.", state, None
            guess = action_payload.get("guess", "").strip().lower()
            state["guesses"].append({"user_id": user_id, "guess": guess})

            if guess == state["secret_word"].lower():
                # Correct guess! Both earn points
                points = max(10, int(60 - (time.time() - state["round_start_time"])))
                if user_id == state["artist_id"]:
                    state["p1_score"] += points
                else:
                    state["p2_score"] += points

                if state["round"] >= state["max_rounds"]:
                    # Match completed
                    winner = state["artist_id"] if state["p1_score"] > state["p2_score"] else state["guesser_id"]
                    if state["p1_score"] == state["p2_score"]:
                        winner = "DRAW"
                    state["winner"] = winner
                    state["status"] = "COMPLETED"
                    return True, f"Correct guess '{guess}'! QuickDraw match completed.", state, winner
                else:
                    # Switch roles for next round
                    state["round"] += 1
                    old_artist = state["artist_id"]
                    state["artist_id"] = state["guesser_id"]
                    state["guesser_id"] = old_artist
                    state["secret_word"] = random.choice([w for w in self.WORD_BANK if w != state["secret_word"]])
                    state["word_length"] = len(state["secret_word"])
                    state["strokes"] = []
                    state["round_start_time"] = time.time()
                    return True, f"Correct! Roles swapped for round 2.", state, None

            return True, f"'{guess}' is incorrect.", state, None

        return False, f"Unknown action '{action_type}'.", state, None

    def get_sanitized_state_for_player(self, current_state: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Never reveal secret sketch word to guesser until match ends."""
        clean = dict(current_state)
        if clean.get("status") != "COMPLETED" and user_id == clean.get("guesser_id"):
            clean["secret_word"] = None  # Hidden!
        return clean


# =============================================================================
# 7. WORD RUSH ENGINE (Shared Letters, Dictionary Validation, Speed Scoring)
# =============================================================================
class WordRushEngine(BasePlayGameEngine):
    """Authoritative Word Rush vocabulary duel engine."""

    DICTIONARY = {
        "cat", "bat", "rat", "mat", "hat", "star", "fast", "post", "stop", "pots",
        "spot", "tops", "read", "dear", "dare", "rate", "tear", "team", "meat",
        "time", "item", "game", "play", "cool", "fire", "water", "earth", "wind",
        "blue", "gold", "mind", "heart", "spark", "light", "super", "magic", "power",
        "words", "rush", "speed", "score", "match", "duels", "quest", "chase", "shine",
    }

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        p1 = player_ids[0] if len(player_ids) > 0 else "p1"
        p2 = player_ids[1] if len(player_ids) > 1 else "p2"
        letters = list("AEIOURSTNLCMPDFG")
        random.shuffle(letters)
        return {
            "p1_id": p1,
            "p2_id": p2,
            "letters": letters[:12],
            "p1_words": [],
            "p2_words": [],
            "p1_score": 0,
            "p2_score": 0,
            "target_score": 50,
            "winner": None,
            "status": "IN_PROGRESS",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("winner"):
            return False, "Match already ended.", state, state.get("winner")

        if action_type != "submit_word":
            return False, f"Unknown action '{action_type}'.", state, None

        word = action_payload.get("word", "").strip().lower()
        if len(word) < 3:
            return False, "Words must be at least 3 letters.", state, None

        all_used = state["p1_words"] + state["p2_words"]
        if word in all_used:
            return False, f"Word '{word}' has already been used in this match.", state, None

        if word not in self.DICTIONARY:
            return False, f"Word '{word}' not recognized in dictionary.", state, None

        pts = len(word) * 10
        if user_id == state["p1_id"]:
            state["p1_words"].append(word)
            state["p1_score"] += pts
        else:
            state["p2_words"].append(word)
            state["p2_score"] += pts

        if state["p1_score"] >= state["target_score"]:
            state["winner"] = state["p1_id"]
            state["status"] = "COMPLETED"
            return True, f"Player 1 reached {state['target_score']} points and won Word Rush!", state, state["p1_id"]
        elif state["p2_score"] >= state["target_score"]:
            state["winner"] = state["p2_id"]
            state["status"] = "COMPLETED"
            return True, f"Player 2 reached {state['target_score']} points and won Word Rush!", state, state["p2_id"]

        return True, f"Valid word '{word}'! +{pts} points.", state, None


# =============================================================================
# 8. BRAIN BLITZ ENGINE (Curated Trivia Bank, Simultaneous Secret Reveal)
# =============================================================================
class BrainBlitzEngine(BasePlayGameEngine):
    """Authoritative Brain Blitz live quiz duel engine."""

    QUESTIONS = [
        {"q": "What is the capital of Japan?", "options": ["Seoul", "Beijing", "Tokyo", "Bangkok"], "correct": 2},
        {"q": "Which element has atomic number 1?", "options": ["Helium", "Hydrogen", "Carbon", "Oxygen"], "correct": 1},
        {"q": "Who painted the Mona Lisa?", "options": ["Van Gogh", "Picasso", "Da Vinci", "Rembrandt"], "correct": 2},
        {"q": "Which planet is known as the Red Planet?", "options": ["Venus", "Jupiter", "Mars", "Saturn"], "correct": 2},
        {"q": "What is the largest ocean on Earth?", "options": ["Atlantic", "Indian", "Arctic", "Pacific"], "correct": 3},
    ]

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        p1 = player_ids[0] if len(player_ids) > 0 else "p1"
        p2 = player_ids[1] if len(player_ids) > 1 else "p2"
        return {
            "p1_id": p1,
            "p2_id": p2,
            "p1_score": 0,
            "p2_score": 0,
            "current_question_index": 0,
            "total_questions": len(self.QUESTIONS),
            "p1_answer": None,
            "p2_answer": None,
            "winner": None,
            "status": "IN_PROGRESS",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("winner"):
            return False, "Brain Blitz battle finished.", state, state.get("winner")

        if action_type != "answer_question":
            return False, f"Invalid action '{action_type}'.", state, None

        chosen_option = action_payload.get("option_index")
        if chosen_option is None or not (0 <= chosen_option <= 3):
            return False, "Option index must be 0, 1, 2, or 3.", state, None

        if user_id == state["p1_id"]:
            state["p1_answer"] = chosen_option
        elif user_id == state["p2_id"]:
            state["p2_answer"] = chosen_option
        else:
            return False, "Unauthorized player.", state, None

        # Check if both have answered
        if state["p1_answer"] is not None and state["p2_answer"] is not None:
            q_idx = state["current_question_index"]
            correct = self.QUESTIONS[q_idx]["correct"]

            if state["p1_answer"] == correct:
                state["p1_score"] += 100
            if state["p2_answer"] == correct:
                state["p2_score"] += 100

            # Advance question or finish
            if q_idx + 1 >= state["total_questions"]:
                winner = state["p1_id"] if state["p1_score"] > state["p2_score"] else state["p2_id"]
                if state["p1_score"] == state["p2_score"]:
                    winner = "DRAW"
                state["winner"] = winner
                state["status"] = "COMPLETED"
                return True, "All questions completed!", state, winner
            else:
                state["current_question_index"] += 1
                state["p1_answer"] = None
                state["p2_answer"] = None
                return True, "Round scored! Advancing to next question.", state, None

        return True, "Answer recorded. Waiting for opponent.", state, None

    def get_sanitized_state_for_player(self, current_state: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Hide correct answer index until revealed."""
        clean = dict(current_state)
        q_idx = clean.get("current_question_index", 0)
        if q_idx < len(self.QUESTIONS):
            q_data = dict(self.QUESTIONS[q_idx])
            if clean.get("status") != "COMPLETED" and (clean.get("p1_answer") is None or clean.get("p2_answer") is None):
                q_data.pop("correct", None)  # Hide answer
            clean["question"] = q_data
        return clean


# =============================================================================
# 9. REFLEX RUSH ENGINE (Server Scheduled Cues, Reaction Timestamps, False-Starts)
# =============================================================================
class ReflexRushEngine(BasePlayGameEngine):
    """Authoritative Reflex Rush speed duel engine."""

    ROUNDS_TO_WIN = 3

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        p1 = player_ids[0] if len(player_ids) > 0 else "p1"
        p2 = player_ids[1] if len(player_ids) > 1 else "p2"
        return {
            "p1_id": p1,
            "p2_id": p2,
            "p1_wins": 0,
            "p2_wins": 0,
            "round": 1,
            "cue_time_ms": int(time.time() * 1000) + random.randint(2000, 4000),
            "p1_time_ms": None,
            "p2_time_ms": None,
            "winner": None,
            "status": "IN_PROGRESS",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("winner"):
            return False, "Match completed.", state, state.get("winner")

        if action_type != "tap":
            return False, f"Unknown action '{action_type}'.", state, None

        tap_ms = action_payload.get("client_timestamp_ms", int(time.time() * 1000))
        cue_ms = state["cue_time_ms"]

        # False start check
        if tap_ms < cue_ms:
            other = state["p2_id"] if user_id == state["p1_id"] else state["p1_id"]
            if other == state["p1_id"]:
                state["p1_wins"] += 1
            else:
                state["p2_wins"] += 1
            msg = f"False start by {user_id}! Round awarded to opponent."
        else:
            reaction = tap_ms - cue_ms
            if user_id == state["p1_id"]:
                state["p1_time_ms"] = reaction
            else:
                state["p2_time_ms"] = reaction

            if state["p1_time_ms"] is not None and state["p2_time_ms"] is not None:
                # Compare
                if state["p1_time_ms"] < state["p2_time_ms"]:
                    state["p1_wins"] += 1
                else:
                    state["p2_wins"] += 1
                msg = f"Round completed! P1: {state['p1_time_ms']}ms vs P2: {state['p2_time_ms']}ms."
            else:
                return True, f"Tap registered ({reaction}ms). Waiting for opponent.", state, None

        # Check win
        if state["p1_wins"] >= self.ROUNDS_TO_WIN:
            state["winner"] = state["p1_id"]
            state["status"] = "COMPLETED"
            return True, "Player 1 won Reflex Rush!", state, state["p1_id"]
        elif state["p2_wins"] >= self.ROUNDS_TO_WIN:
            state["winner"] = state["p2_id"]
            state["status"] = "COMPLETED"
            return True, "Player 2 won Reflex Rush!", state, state["p2_id"]

        # Setup next round
        state["round"] += 1
        state["cue_time_ms"] = int(time.time() * 1000) + random.randint(2000, 4000)
        state["p1_time_ms"] = None
        state["p2_time_ms"] = None
        return True, msg, state, None


# =============================================================================
# 10. MINDMATCH ENGINE (Social Guessing, Synchronized Reveal, Icebreakers)
# =============================================================================
class MindMatchEngine(BasePlayGameEngine):
    """Authoritative MindMatch social compatibility duel engine."""

    DILEMMAS = [
        {"prompt": "Your ideal escape:", "a": "Beach Sunset 🏖️", "b": "Mountain Cabin 🏔️"},
        {"prompt": "Night owl or morning bird?", "a": "Early Sunrise 🌅", "b": "Midnight Stargazer 🌙"},
        {"prompt": "Flavor preference:", "a": "Spicy Delights 🌶️", "b": "Sweet Indulgence 🍫"},
        {"prompt": "Vacation style:", "a": "Action & Adventure 🧗", "b": "Peace & Relaxation 🧘"},
        {"prompt": "Weekend vibe:", "a": "Lively Party 🎉", "b": "Quiet Movie Night 🍿"},
    ]

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        p1 = player_ids[0] if len(player_ids) > 0 else "p1"
        p2 = player_ids[1] if len(player_ids) > 1 else "p2"
        return {
            "p1_id": p1,
            "p2_id": p2,
            "round": 0,
            "total_rounds": len(self.DILEMMAS),
            "match_score": 0,
            "p1_choice": None,
            "p2_choice": None,
            "conversation_starters": [],
            "winner": None,
            "status": "IN_PROGRESS",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("winner"):
            return False, "MindMatch session completed.", state, state.get("winner")

        if action_type != "select_option":
            return False, f"Unknown action '{action_type}'.", state, None

        choice = action_payload.get("choice")  # 'a' or 'b'
        if choice not in ("a", "b"):
            return False, "Choice must be 'a' or 'b'.", state, None

        if user_id == state["p1_id"]:
            state["p1_choice"] = choice
        elif user_id == state["p2_id"]:
            state["p2_choice"] = choice

        if state["p1_choice"] and state["p2_choice"]:
            # Evaluate match
            is_match = state["p1_choice"] == state["p2_choice"]
            if is_match:
                state["match_score"] += 20
                state["conversation_starters"].append(f"Both chose '{state['p1_choice'].upper()}' on round {state['round'] + 1}!")

            if state["round"] + 1 >= state["total_rounds"]:
                state["winner"] = "COOP_SUCCESS"
                state["status"] = "COMPLETED"
                return True, f"MindMatch finished! Compatibility score: {state['match_score']}%.", state, "COOP_SUCCESS"
            else:
                state["round"] += 1
                state["p1_choice"] = None
                state["p2_choice"] = None
                return True, f"Match revealed! Current score: {state['match_score']}%.", state, None

        return True, "Choice submitted. Waiting for partner.", state, None

    def get_sanitized_state_for_player(self, current_state: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Never reveal partner's choice before both have picked."""
        clean = dict(current_state)
        r = clean.get("round", 0)
        if r < len(self.DILEMMAS):
            clean["current_dilemma"] = self.DILEMMAS[r]

        if clean.get("p1_choice") is None or clean.get("p2_choice") is None:
            if user_id == clean.get("p1_id"):
                clean["p2_choice"] = None
                clean["partner_choice"] = None
            else:
                clean["p1_choice"] = None
                clean["partner_choice"] = None
        return clean


# =============================================================================
# 11. MYSTERY MISSION ENGINE (Cooperative Deduction, Private & Shared Clues)
# =============================================================================
class MysteryMissionEngine(BasePlayGameEngine):
    """Authoritative Mystery Mission cooperative duel engine."""

    STAGES = [
        {
            "prompt": "Stage 1: The Locked Study",
            "clue_a": "There are 3 silver keys on the wall.",
            "clue_b": "The passcode is the number of keys multiplied by 4.",
            "answer": "12",
        },
        {
            "prompt": "Stage 2: The Cipher Vault",
            "clue_a": "The word starts with 'S' and has 4 letters.",
            "clue_b": "It is something you see in the night sky.",
            "answer": "star",
        },
        {
            "prompt": "Stage 3: The Escape Hatch",
            "clue_a": "The color is neither red nor green.",
            "clue_b": "It is the color of the deep LikBy ocean.",
            "answer": "blue",
        },
    ]

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        p1 = player_ids[0] if len(player_ids) > 0 else "p1"
        p2 = player_ids[1] if len(player_ids) > 1 else "p2"
        return {
            "p1_id": p1,
            "p2_id": p2,
            "stage": 0,
            "total_stages": len(self.STAGES),
            "hints_used": 0,
            "winner": None,
            "status": "IN_PROGRESS",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("winner"):
            return False, "Mystery Mission already solved.", state, state.get("winner")

        if action_type != "submit_solution":
            return False, f"Unknown action '{action_type}'.", state, None

        answer = str(action_payload.get("answer", "")).strip().lower()
        curr_stage = self.STAGES[state["stage"]]

        if answer == curr_stage["answer"].lower():
            if state["stage"] + 1 >= state["total_stages"]:
                state["winner"] = "COOP_VICTORY"
                state["status"] = "COMPLETED"
                return True, "Mystery solved! Both players escaped successfully!", state, "COOP_VICTORY"
            else:
                state["stage"] += 1
                return True, "Stage completed! Unlocking next chamber.", state, None
        return False, "Incorrect solution. Review your clues together!", state, None

    def get_sanitized_state_for_player(self, current_state: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Player A receives clue_a, Player B receives clue_b!"""
        clean = dict(current_state)
        stg_idx = clean.get("stage", 0)
        if stg_idx < len(self.STAGES):
            stage = self.STAGES[stg_idx]
            clean["prompt"] = stage["prompt"]
            if user_id == clean.get("p1_id"):
                clean["private_clue"] = stage["clue_a"]
                clean["my_clue"] = stage["clue_a"]
            else:
                clean["private_clue"] = stage["clue_b"]
                clean["my_clue"] = stage["clue_b"]
        return clean


# =============================================================================
# 12. XO (TIC-TAC-TOE) ENGINE (3x3 Grid, Cyber-Neon Strategy, Alternating Turns)
# =============================================================================
class XOEngine(BasePlayGameEngine):
    """Authoritative XO (Tic-Tac-Toe) duel engine."""

    GRID_SIZE = 3

    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        p1 = player_ids[0] if len(player_ids) > 0 else "player_1"
        p2 = player_ids[1] if len(player_ids) > 1 else "player_2"
        return {
            "board": [["" for _ in range(self.GRID_SIZE)] for _ in range(self.GRID_SIZE)],
            "player_x": p1,
            "player_o": p2,
            "current_turn": p1,
            "move_count": 0,
            "winner": None,
            "winning_cells": [],
            "status": "IN_PROGRESS",
        }

    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        state = dict(current_state)
        if state.get("winner") or state.get("status") == "COMPLETED":
            return False, "Game is already completed.", state, state.get("winner")

        if action_type not in ("place_mark", "make_move"):
            return False, f"Unknown action type '{action_type}'.", state, None

        if user_id != state.get("current_turn"):
            return False, "It is not your turn.", state, None

        # Accept either {"row": r, "col": c} or {"cell": 0..8}
        if "cell" in action_payload:
            try:
                cell = int(action_payload["cell"])
                row, col = cell // self.GRID_SIZE, cell % self.GRID_SIZE
            except (ValueError, TypeError):
                return False, "Invalid cell index.", state, None
        else:
            row = action_payload.get("row")
            col = action_payload.get("col")

        if row is None or col is None or not (0 <= row < self.GRID_SIZE and 0 <= col < self.GRID_SIZE):
            return False, "Row and column must be integers between 0 and 2.", state, None

        board = [list(r) for r in state["board"]]
        if board[row][col] != "":
            return False, f"Cell ({row}, {col}) is already occupied.", state, None

        mark = "X" if user_id == state["player_x"] else "O"
        board[row][col] = mark
        state["board"] = board
        state["move_count"] = state.get("move_count", 0) + 1

        # Check win condition
        has_won, winning_cells = self._check_win(board, mark)
        if has_won:
            state["winner"] = user_id
            state["winning_cells"] = winning_cells
            state["status"] = "COMPLETED"
            return True, f"Player {mark} aligned 3 marks and won!", state, user_id

        # Check draw condition
        if state["move_count"] >= self.GRID_SIZE * self.GRID_SIZE:
            state["winner"] = "DRAW"
            state["status"] = "COMPLETED"
            return True, "Board is full. Match ended in a draw.", state, "DRAW"

        # Toggle turn
        state["current_turn"] = state["player_o"] if user_id == state["player_x"] else state["player_x"]
        return True, f"Mark {mark} placed at ({row}, {col}).", state, None

    def _check_win(self, board: List[List[str]], mark: str) -> Tuple[bool, List[List[int]]]:
        # Rows
        for r in range(self.GRID_SIZE):
            if board[r][0] == board[r][1] == board[r][2] == mark:
                return True, [[r, 0], [r, 1], [r, 2]]
        # Columns
        for c in range(self.GRID_SIZE):
            if board[0][c] == board[1][c] == board[2][c] == mark:
                return True, [[0, c], [1, c], [2, c]]
        # Main diagonal
        if board[0][0] == board[1][1] == board[2][2] == mark:
            return True, [[0, 0], [1, 1], [2, 2]]
        # Anti-diagonal
        if board[0][2] == board[1][1] == board[2][0] == mark:
            return True, [[0, 2], [1, 1], [2, 0]]

        return False, []

