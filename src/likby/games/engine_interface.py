"""
likby.games.engine_interface
Abstract engine contract for all 17 LikBy Play multiplayer duels and solo games.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class BasePlayGameEngine(ABC):
    """Authoritative server-side game rules, state progression, and sanitized view engine."""

    @abstractmethod
    def init_game_state(self, config: Dict[str, Any], player_ids: List[str]) -> Dict[str, Any]:
        """Generate initial authoritative state dictionary for a new match."""
        pass

    @abstractmethod
    def process_action(
        self,
        current_state: Dict[str, Any],
        user_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        """
        Validate and execute player action against game rules.
        Returns:
            (is_valid: bool, message: str, updated_state: dict, winner_id: Optional[str])
        """
        pass

    def get_sanitized_state_for_player(
        self,
        current_state: Dict[str, Any],
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Filter out opponent-only secret information (e.g. unrevealed trivia answers,
        secret sketch word in QuickDraw, private cooperative clues in Mystery Mission).
        Default implementation returns full state.
        """
        return current_state
