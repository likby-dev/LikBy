"""
likby.domain.entities.play_game
Authoritative game catalogue, state definitions, participants, invitations, and quota tracking for LikBy Play.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from likby.domain.enums import (
    DuelParticipantRole,
    GameInvitationStatus,
    GameMode,
    GameType,
    PlaySessionStatus,
    SubscriptionTier,
)


class GameDefinition(BaseModel):
    """Static catalog definition of a playable LikBy Play game."""

    id: GameType
    name: str
    mode: GameMode
    category: str
    typical_duration: str
    tagline: str
    description: str
    min_players: int = 1
    max_players: int = 2
    rules_version: int = 1
    config: Dict[str, Any] = Field(default_factory=dict)


# Authoritative Catalogue of 17 Games (11 Duels + 6 Solos)
GAME_CATALOGUE: Dict[GameType, GameDefinition] = {
    # -------------------------------------------------------------------------
    # 11 Multiplayer Duel Games
    # -------------------------------------------------------------------------
    GameType.CARROM_CLASH: GameDefinition(
        id=GameType.CARROM_CLASH,
        name="Carrom Clash",
        mode=GameMode.DUEL,
        category="Physics & Tabletop",
        typical_duration="3–7 min",
        tagline="Smooth striker carrom physics with legal queen rules",
        description="Two players compete on a digital carrom board. Strike coins with precision and claim the queen.",
        min_players=2,
        max_players=2,
        config={"board_size": 400, "coins_white": 9, "coins_black": 9, "queen": 1, "points_to_win": 25},
    ),
    GameType.AIR_RUSH: GameDefinition(
        id=GameType.AIR_RUSH,
        name="Air Rush",
        mode=GameMode.DUEL,
        category="Arcade Sports",
        typical_duration="1–3 min",
        tagline="Fast-paced air-hockey duel with responsive paddles",
        description="Defend your goal and blast the puck into the opponent's net. First to target score wins.",
        min_players=2,
        max_players=2,
        config={"target_score": 5, "puck_speed": 400, "friction": 0.99},
    ),
    GameType.POCKET_POOL: GameDefinition(
        id=GameType.POCKET_POOL,
        name="Pocket Pool",
        mode=GameMode.DUEL,
        category="Precision & Strategy",
        typical_duration="3–8 min",
        tagline="Tactical 8-ball billiards with realistic collision angles",
        description="Aim the cue, control shot power, and pot your designated group before sinking the 8-ball.",
        min_players=2,
        max_players=2,
        config={"balls_count": 16, "friction": 0.985, "cushion_restitution": 0.8},
    ),
    GameType.STICK_ARENA: GameDefinition(
        id=GameType.STICK_ARENA,
        name="Stick Arena",
        mode=GameMode.DUEL,
        category="Casual Action",
        typical_duration="1–3 min",
        tagline="Playful non-graphic 2D platform brawler",
        description="Jump, dodge, and execute combo attacks to knock your opponent off the arena platform.",
        min_players=2,
        max_players=2,
        config={"initial_hp": 100, "arena_width": 600, "arena_height": 400},
    ),
    GameType.QUICKDRAW: GameDefinition(
        id=GameType.QUICKDRAW,
        name="QuickDraw",
        mode=GameMode.DUEL,
        category="Drawing & Guessing",
        typical_duration="2–5 min",
        tagline="Real-time drawing canvas with synchronized stroke events",
        description="One player sketches a secret server-selected word while the other races against time to guess it.",
        min_players=2,
        max_players=2,
        config={"round_time_seconds": 60, "total_rounds": 4, "max_hints": 3},
    ),
    GameType.WORD_RUSH: GameDefinition(
        id=GameType.WORD_RUSH,
        name="Word Rush",
        mode=GameMode.DUEL,
        category="Word Competition",
        typical_duration="1–3 min",
        tagline="Fast-paced vocabulary race against shared letter pools",
        description="Compete to submit valid English dictionary words from a shared grid before your partner.",
        min_players=2,
        max_players=2,
        config={"round_time_seconds": 90, "min_word_length": 3, "combo_multiplier": 1.5},
    ),
    GameType.BRAIN_BLITZ: GameDefinition(
        id=GameType.BRAIN_BLITZ,
        name="Brain Blitz",
        mode=GameMode.DUEL,
        category="Trivia & Knowledge",
        typical_duration="2–4 min",
        tagline="Curated quiz battles with simultaneous secret answer reveals",
        description="Both players answer the same question simultaneously. High speed and accuracy yield streak bonuses.",
        min_players=2,
        max_players=2,
        config={"questions_per_match": 5, "time_per_question": 15, "streak_bonus": 50},
    ),
    GameType.REFLEX_RUSH: GameDefinition(
        id=GameType.REFLEX_RUSH,
        name="Reflex Rush",
        mode=GameMode.DUEL,
        category="Reaction Speed",
        typical_duration="30–90 sec",
        tagline="Sub-millisecond reaction challenge with false-start detection",
        description="Wait for the random server cue and tap as fast as possible. Best reaction time across rounds wins.",
        min_players=2,
        max_players=2,
        config={"rounds": 5, "min_delay_ms": 1500, "max_delay_ms": 4000},
    ),
    GameType.CONNECT_FOUR: GameDefinition(
        id=GameType.CONNECT_FOUR,
        name="Connect Four",
        mode=GameMode.DUEL,
        category="Strategy",
        typical_duration="2–5 min",
        tagline="Deterministic 7x6 board strategy with alternating drop turns",
        description="Drop colored discs into a 7-column grid. Connect four pieces horizontally, vertically, or diagonally.",
        min_players=2,
        max_players=2,
        config={"rows": 6, "cols": 7, "turn_time_seconds": 30},
    ),
    GameType.MINDMATCH: GameDefinition(
        id=GameType.MINDMATCH,
        name="MindMatch",
        mode=GameMode.DUEL,
        category="Social Discovery",
        typical_duration="2–4 min",
        tagline="Social compatibility guessing with conversation starters",
        description="Pick your personal choice on life, travel, and preferences. Discover how similarly you and your partner think.",
        min_players=2,
        max_players=2,
        config={"rounds": 5, "categories": ["lifestyle", "travel", "philosophy", "fun"]},
    ),
    GameType.MYSTERY_MISSION: GameDefinition(
        id=GameType.MYSTERY_MISSION,
        name="Mystery Mission",
        mode=GameMode.COOP_DUEL,
        category="Cooperative Deduction",
        typical_duration="3–7 min",
        tagline="Cooperative mystery solving with private and shared clues",
        description="Work together to solve an escape mystery. Combine clue fragments that only one of you can see.",
        min_players=2,
        max_players=2,
        config={"max_time_seconds": 300, "stages": 3, "hints_allowed": 2},
    ),

    # -------------------------------------------------------------------------
    # 6 Solo Games (Unlimited Daily Access for All Tiers)
    # -------------------------------------------------------------------------
    GameType.ZEN_MERGE: GameDefinition(
        id=GameType.ZEN_MERGE,
        name="Zen Merge",
        mode=GameMode.SOLO,
        category="Number Puzzle",
        typical_duration="Flexible",
        tagline="Relaxing 2048 number-merging puzzle with smooth tile physics",
        description="Slide and combine matching numbers to reach higher values. Unlimited daily play.",
        min_players=1,
        max_players=1,
        config={"grid_size": 4, "target_tile": 2048, "undo_limit": 3},
    ),
    GameType.WORD_HUNT: GameDefinition(
        id=GameType.WORD_HUNT,
        name="Word Hunt",
        mode=GameMode.SOLO,
        category="Word Search",
        typical_duration="Flexible",
        tagline="Classic word search grid across curated themed categories",
        description="Find hidden words placed horizontally, vertically, or diagonally in letter grids. Unlimited plays.",
        min_players=1,
        max_players=1,
        config={"grid_size": 8, "words_count": 6},
    ),
    GameType.COLOR_FLOW: GameDefinition(
        id=GameType.COLOR_FLOW,
        name="Color Flow",
        mode=GameMode.SOLO,
        category="Visual Logic",
        typical_duration="Flexible",
        tagline="Connect matching colors with non-overlapping pipe paths",
        description="Connect matching color dots without overlapping lines. Features accessible symbol support.",
        min_players=1,
        max_players=1,
        config={"grid_sizes": [5, 6, 7], "levels_count": 20},
    ),
    GameType.POCKET_GOLF: GameDefinition(
        id=GameType.POCKET_GOLF,
        name="Pocket Golf",
        mode=GameMode.SOLO,
        category="Arcade Physics",
        typical_duration="Flexible",
        tagline="Miniature golf obstacle courses with drag-to-aim controls",
        description="Aim and strike the golf ball through compact obstacles into the hole with minimal strokes.",
        min_players=1,
        max_players=1,
        config={"holes": 9, "max_strokes_per_hole": 8},
    ),
    GameType.REFLEX_LAB: GameDefinition(
        id=GameType.REFLEX_LAB,
        name="Reflex Lab",
        mode=GameMode.SOLO,
        category="Focus & Memory",
        typical_duration="Flexible",
        tagline="Cognitive exercises: reaction time, sequence memory, and odd-one-out",
        description="Test your reaction time, sequence recall, and pattern recognition. Personal stats tracked.",
        min_players=1,
        max_players=1,
        config={"modes": ["reaction", "sequence", "odd_symbol", "tracker"]},
    ),
    GameType.DAILY_MYSTERY: GameDefinition(
        id=GameType.DAILY_MYSTERY,
        name="Daily Mystery",
        mode=GameMode.SOLO,
        category="Logic Deduction",
        typical_duration="Flexible",
        tagline="Featured daily logic puzzle with clues and deduction grid",
        description="Solve a featured daily deduction riddle using logical elimination. Includes unlimited practice mode.",
        min_players=1,
        max_players=1,
        config={"clues_count": 4, "hints_limit": 2},
    ),
}


class PlayGameSession(BaseModel):
    """Authoritative game session for LikBy Play multiplayer duels and solo games."""

    id: str = Field(..., description="Unique play session ID e.g. play_01K8...")
    game_id: GameType
    mode: GameMode
    status: PlaySessionStatus = Field(default=PlaySessionStatus.CREATED)
    rules_version: int = Field(default=1)
    state_data: Dict[str, Any] = Field(default_factory=dict, description="Game-specific authoritative state")
    current_turn_user_id: Optional[str] = None
    round_number: int = Field(default=1)
    max_rounds: int = Field(default=1)
    winner_id: Optional[str] = None
    result_summary: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_active(self) -> bool:
        return self.status in (PlaySessionStatus.ACTIVE, PlaySessionStatus.STARTING)

    def can_transition_to(self, new_status: PlaySessionStatus) -> bool:
        """Enforces explicit state machine transitions."""
        valid_transitions = {
            PlaySessionStatus.CREATED: [PlaySessionStatus.INVITED, PlaySessionStatus.STARTING, PlaySessionStatus.CANCELLED],
            PlaySessionStatus.INVITED: [PlaySessionStatus.ACCEPTED, PlaySessionStatus.REJECTED, PlaySessionStatus.EXPIRED, PlaySessionStatus.CANCELLED],
            PlaySessionStatus.ACCEPTED: [PlaySessionStatus.STARTING, PlaySessionStatus.CANCELLED],
            PlaySessionStatus.STARTING: [PlaySessionStatus.ACTIVE, PlaySessionStatus.CANCELLED],
            PlaySessionStatus.ACTIVE: [PlaySessionStatus.PAUSED, PlaySessionStatus.COMPLETED, PlaySessionStatus.ABANDONED],
            PlaySessionStatus.PAUSED: [PlaySessionStatus.ACTIVE, PlaySessionStatus.COMPLETED, PlaySessionStatus.ABANDONED],
            PlaySessionStatus.COMPLETED: [],
            PlaySessionStatus.CANCELLED: [],
            PlaySessionStatus.EXPIRED: [],
            PlaySessionStatus.ABANDONED: [],
        }
        return new_status in valid_transitions.get(self.status, [])


class GameParticipant(BaseModel):
    """Participant in a LikBy Play game session."""

    game_session_id: str
    user_id: str
    role: DuelParticipantRole = Field(default=DuelParticipantRole.CHALLENGER)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    final_score: int = Field(default=0)
    is_winner: bool = Field(default=False)


class GameInvitation(BaseModel):
    """Time-limited duel challenge invitation."""

    id: str = Field(..., description="Invitation reference e.g. inv_01K8...")
    sender_id: str
    recipient_id: str
    game_id: GameType
    status: GameInvitationStatus = Field(default=GameInvitationStatus.PENDING)
    session_id: Optional[str] = None
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DuelQuotaUsage(BaseModel):
    """Durable record of a consumed duel credit."""

    id: str
    user_id: str
    game_session_id: str
    subscription_tier_snapshot: SubscriptionTier
    quota_period_start: str
    quota_period_end: str
    consumed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    idempotency_key: str


class GameStatistic(BaseModel):
    """Aggregate game metrics for a user."""

    user_id: str
    game_id: GameType
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    high_score: int = 0
    last_played_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
