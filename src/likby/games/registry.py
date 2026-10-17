"""
likby.games.registry
Engine registry mapping all 17 LikBy Play games to their authoritative rules engines.
"""

from typing import Dict, Optional

from likby.domain.enums import GameType
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
from likby.games.engine_interface import BasePlayGameEngine
from likby.games.solo_engines import (
    ColorFlowEngine,
    DailyMysteryEngine,
    PocketGolfEngine,
    ReflexLabEngine,
    WordHuntEngine,
    ZenMergeEngine,
)


_GAME_ENGINES: Dict[GameType, BasePlayGameEngine] = {
    # 11 Multiplayer Duels
    GameType.CONNECT_FOUR: ConnectFourEngine(),
    GameType.CARROM_CLASH: CarromClashEngine(),
    GameType.AIR_RUSH: AirRushEngine(),
    GameType.POCKET_POOL: PocketPoolEngine(),
    GameType.STICK_ARENA: StickArenaEngine(),
    GameType.QUICKDRAW: QuickDrawEngine(),
    GameType.WORD_RUSH: WordRushEngine(),
    GameType.BRAIN_BLITZ: BrainBlitzEngine(),
    GameType.REFLEX_RUSH: ReflexRushEngine(),
    GameType.MINDMATCH: MindMatchEngine(),
    GameType.MYSTERY_MISSION: MysteryMissionEngine(),

    # 6 Solo Games
    GameType.ZEN_MERGE: ZenMergeEngine(),
    GameType.WORD_HUNT: WordHuntEngine(),
    GameType.COLOR_FLOW: ColorFlowEngine(),
    GameType.POCKET_GOLF: PocketGolfEngine(),
    GameType.REFLEX_LAB: ReflexLabEngine(),
    GameType.DAILY_MYSTERY: DailyMysteryEngine(),
}


def get_game_engine(game_type: GameType) -> Optional[BasePlayGameEngine]:
    """Retrieve the authoritative game engine for a specified GameType."""
    return _GAME_ENGINES.get(game_type)


def get_duel_engine(game_type: GameType) -> Optional[BasePlayGameEngine]:
    """Retrieve duel game engine."""
    return _GAME_ENGINES.get(game_type)


def get_solo_engine(game_type: GameType) -> Optional[BasePlayGameEngine]:
    """Retrieve solo game engine."""
    return _GAME_ENGINES.get(game_type)


def list_available_games():
    """List all 17 registered game types."""
    return list(_GAME_ENGINES.keys())
