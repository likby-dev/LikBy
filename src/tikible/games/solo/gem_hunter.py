"""
tikible.games.solo.gem_hunter
Fast-paced 3x3 Gem Hunter (Mini Minesweeper) single-player game.
"""

from dataclasses import dataclass, field
import random
from typing import List, Optional, Tuple


@dataclass
class GemHunterGame:
    """A single player 3x3 grid where 8 tiles contain gems and 1 contains a bomb."""
    bomb_row: int
    bomb_col: int
    revealed: List[List[bool]] = field(
        default_factory=lambda: [[False, False, False], [False, False, False], [False, False, False]]
    )
    score: int = 0
    is_over: bool = False
    hit_bomb: bool = False

    @classmethod
    def start_new(cls) -> "GemHunterGame":
        return cls(
            bomb_row=random.randint(0, 2),
            bomb_col=random.randint(0, 2),
        )

    def reveal(self, row: int, col: int) -> Tuple[bool, bool]:
        """
        Reveal tile (row, col).
        Returns (is_bomb, is_win).
        """
        if self.is_over:
            return self.hit_bomb, False

        if not (0 <= row <= 2 and 0 <= col <= 2):
            return False, False

        if self.revealed[row][col]:
            return False, False

        self.revealed[row][col] = True

        if row == self.bomb_row and col == self.bomb_col:
            self.hit_bomb = True
            self.is_over = True
            return True, False

        self.score += 10
        # Check if all 8 non-bomb tiles are revealed
        revealed_count = sum(sum(1 for c in r if c) for r in self.revealed)
        if revealed_count == 8:
            self.is_over = True
            self.score += 50  # Bonus for clearing all gems!
            return False, True

        return False, False
