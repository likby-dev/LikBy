"""
likby.services.progression_service
Shared progression, player leveling, achievements, personal records,
and leaderboard engine for LikBy GameVerse.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from likby.domain.enums import GameType


class AchievementDefinition(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    xp_reward: int
    category: str


ACHIEVEMENTS_CATALOG: Dict[str, AchievementDefinition] = {
    "first_victory": AchievementDefinition(
        id="first_victory",
        name="First Blood",
        description="Claim your first multiplayer duel victory in LikBy GameVerse.",
        icon="⚔️",
        xp_reward=100,
        category="Multiplayer",
    ),
    "streak_master": AchievementDefinition(
        id="streak_master",
        name="Hot Streak",
        description="Win 3 consecutive multiplayer duels without defeat.",
        icon="🔥",
        xp_reward=250,
        category="Competitive",
    ),
    "sharpshooter": AchievementDefinition(
        id="sharpshooter",
        name="Sharpshooter",
        description="Execute a precision trick shot in Carrom Clash or Pocket Pool.",
        icon="🎯",
        xp_reward=150,
        category="Physics",
    ),
    "brain_box": AchievementDefinition(
        id="brain_box",
        name="Trivia Titan",
        description="Score 300+ points in a single Brain Blitz duel match.",
        icon="🧠",
        xp_reward=150,
        category="Trivia",
    ),
    "swift_fingers": AchievementDefinition(
        id="swift_fingers",
        name="Lightning Reflexes",
        description="Clock a reaction time under 250ms in Reflex Rush or Reflex Lab.",
        icon="⚡",
        xp_reward=150,
        category="Reaction",
    ),
    "puzzle_genius": AchievementDefinition(
        id="puzzle_genius",
        name="Zen Master",
        description="Merge and forge a 512+ value tile in Zen Merge.",
        icon="🧩",
        xp_reward=200,
        category="Solo Puzzle",
    ),
    "lexicon_hero": AchievementDefinition(
        id="lexicon_hero",
        name="Word Wizard",
        description="Discover 5+ target words in Word Hunt or score 50+ in Word Rush.",
        icon="🔤",
        xp_reward=150,
        category="Vocabulary",
    ),
    "coop_detective": AchievementDefinition(
        id="coop_detective",
        name="Safe Cracker",
        description="Successfully crack the Mystery Mission classified safe with your partner.",
        icon="🔐",
        xp_reward=200,
        category="Cooperative",
    ),
    "daily_challenger": AchievementDefinition(
        id="daily_challenger",
        name="Cryptic Mind",
        description="Decipher and solve today's canonical Daily Mystery riddle.",
        icon="📜",
        xp_reward=150,
        category="Daily Challenge",
    ),
    "social_butterfly": AchievementDefinition(
        id="social_butterfly",
        name="Soul Sync",
        description="Achieve 80%+ harmony compatibility in MindMatch.",
        icon="💙",
        xp_reward=120,
        category="Social",
    ),
}


class UserProgression(BaseModel):
    user_id: str
    total_xp: int = 0
    level: int = 1
    xp_to_next_level: int = 200
    level_progress_percent: int = 0
    total_duels_played: int = 0
    total_duels_won: int = 0
    total_solo_played: int = 0
    current_streak: int = 0
    best_streak: int = 0
    unlocked_achievements: Set[str] = Field(default_factory=set)
    game_high_scores: Dict[str, int] = Field(default_factory=dict)
    daily_streak: int = 0
    last_played_at: Optional[datetime] = None


class ProgressionService:
    """
    Authoritative server-side progression authority. Calculates levels,
    evaluates achievements, records streaks, and manages leaderboards.
    """

    def __init__(self) -> None:
        self._profiles: Dict[str, UserProgression] = {}

    def get_or_create_progression(self, user_id: str) -> UserProgression:
        if user_id not in self._profiles:
            self._profiles[user_id] = UserProgression(user_id=user_id)
        return self._profiles[user_id]

    def record_duel_completion(
        self,
        user_id: str,
        game_id: GameType,
        is_winner: bool,
        is_draw: bool = False,
        score: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[UserProgression, List[AchievementDefinition]]:
        """
        Record completion of a multiplayer duel. Awards XP, updates streaks,
        evaluates achievements, and returns newly unlocked awards.
        """
        prog = self.get_or_create_progression(user_id)
        prog.total_duels_played += 1
        prog.last_played_at = datetime.now(timezone.utc)

        # Base duel XP
        awarded_xp = 50

        if is_winner:
            prog.total_duels_won += 1
            prog.current_streak += 1
            if prog.current_streak > prog.best_streak:
                prog.best_streak = prog.current_streak
            awarded_xp += 100
        elif not is_draw:
            prog.current_streak = 0
        else:
            awarded_xp += 25

        # Update high score for this game
        g_key = game_id.value
        if score > prog.game_high_scores.get(g_key, 0):
            prog.game_high_scores[g_key] = score

        prog.total_xp += awarded_xp
        self._recalculate_level(prog)

        # Check achievements
        newly_unlocked = self._evaluate_achievements(prog, game_id, is_winner, score, metadata or {})
        return prog, newly_unlocked

    def record_solo_completion(
        self,
        user_id: str,
        game_id: GameType,
        score: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[UserProgression, List[AchievementDefinition]]:
        """Record solo game accomplishment and award progression XP."""
        prog = self.get_or_create_progression(user_id)
        prog.total_solo_played += 1
        prog.last_played_at = datetime.now(timezone.utc)

        awarded_xp = 75
        g_key = game_id.value
        if score > prog.game_high_scores.get(g_key, 0):
            prog.game_high_scores[g_key] = score

        prog.total_xp += awarded_xp
        self._recalculate_level(prog)

        newly_unlocked = self._evaluate_achievements(prog, game_id, False, score, metadata or {})
        return prog, newly_unlocked

    def get_user_overview(self, user_id: str) -> Dict[str, Any]:
        """Produce client-facing progression and achievement overview."""
        prog = self.get_or_create_progression(user_id)
        return {
            "user_id": prog.user_id,
            "level": prog.level,
            "total_xp": prog.total_xp,
            "xp_to_next_level": prog.xp_to_next_level,
            "progress_percent": prog.level_progress_percent,
            "total_duels_played": prog.total_duels_played,
            "total_duels_won": prog.total_duels_won,
            "win_rate": (
                round((prog.total_duels_won / prog.total_duels_played) * 100, 1)
                if prog.total_duels_played > 0
                else 0.0
            ),
            "current_streak": prog.current_streak,
            "best_streak": prog.best_streak,
            "achievements_count": len(prog.unlocked_achievements),
            "achievements_total": len(ACHIEVEMENTS_CATALOG),
            "unlocked_achievement_ids": list(prog.unlocked_achievements),
            "high_scores": prog.game_high_scores,
        }

    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return global top players by XP and level."""
        sorted_profiles = sorted(
            self._profiles.values(),
            key=lambda p: (p.level, p.total_xp, p.total_duels_won),
            reverse=True,
        )[:limit]

        return [
            {
                "rank": idx + 1,
                "user_id": p.user_id,
                "level": p.level,
                "total_xp": p.total_xp,
                "wins": p.total_duels_won,
                "games_played": p.total_duels_played,
            }
            for idx, p in enumerate(sorted_profiles)
        ]

    def _recalculate_level(self, prog: UserProgression) -> None:
        """
        Calculates progressive level based on square-root scaling curve:
        Level 1: 0 XP
        Level 2: 200 XP
        Level 3: 500 XP
        Level 4: 900 XP ...
        """
        xp = prog.total_xp
        # Threshold: 100 * level * (level + 1)
        level = 1
        while 100 * level * (level + 1) <= xp:
            level += 1

        prog.level = level
        current_level_base = 100 * (level - 1) * level
        next_level_target = 100 * level * (level + 1)
        level_range = next_level_target - current_level_base
        xp_in_level = max(0, xp - current_level_base)

        prog.xp_to_next_level = max(0, next_level_target - xp)
        prog.level_progress_percent = min(100, int((xp_in_level / level_range) * 100)) if level_range > 0 else 0

    def _evaluate_achievements(
        self,
        prog: UserProgression,
        game_id: GameType,
        is_winner: bool,
        score: int,
        metadata: Dict[str, Any],
    ) -> List[AchievementDefinition]:
        """Idempotently unlock qualifying achievements and grant bonus XP."""
        unlocked_now: List[AchievementDefinition] = []

        def grant(ach_id: str) -> None:
            if ach_id not in prog.unlocked_achievements and ach_id in ACHIEVEMENTS_CATALOG:
                prog.unlocked_achievements.add(ach_id)
                ach = ACHIEVEMENTS_CATALOG[ach_id]
                prog.total_xp += ach.xp_reward
                self._recalculate_level(prog)
                unlocked_now.append(ach)

        # 1. First Victory
        if is_winner and prog.total_duels_won >= 1:
            grant("first_victory")

        # 2. Hot Streak
        if prog.current_streak >= 3:
            grant("streak_master")

        # 3. Sharpshooter
        if game_id in (GameType.CARROM_CLASH, GameType.POCKET_POOL) and (score >= 20 or metadata.get("potted_count", 0) >= 2):
            grant("sharpshooter")

        # 4. Brain Box
        if game_id == GameType.BRAIN_BLITZ and score >= 300:
            grant("brain_box")

        # 5. Swift Fingers
        if game_id in (GameType.REFLEX_RUSH, GameType.REFLEX_LAB) and (0 < metadata.get("reaction_ms", 999) < 250):
            grant("swift_fingers")

        # 6. Puzzle Genius
        if game_id == GameType.ZEN_MERGE and (score >= 512 or metadata.get("highest_tile", 0) >= 512):
            grant("puzzle_genius")

        # 7. Lexicon Hero
        if (game_id == GameType.WORD_HUNT and metadata.get("words_found_count", 0) >= 5) or (game_id == GameType.WORD_RUSH and score >= 50):
            grant("lexicon_hero")

        # 8. Coop Detective
        if game_id == GameType.MYSTERY_MISSION and metadata.get("safe_unlocked", False):
            grant("coop_detective")

        # 9. Daily Challenger
        if game_id == GameType.DAILY_MYSTERY and metadata.get("solved", False):
            grant("daily_challenger")

        # 10. Social Butterfly
        if game_id == GameType.MINDMATCH and score >= 80:
            grant("social_butterfly")

        return unlocked_now
