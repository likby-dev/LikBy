"""
likby.domain.entities.game
GameSession entity and server-authoritative Tic-Tac-Toe game engine.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from likby.domain.enums import GameStatus, GameType


class InvalidMoveError(Exception):
    """Raised when an illegal move is attempted."""
    pass


class NotYourTurnError(Exception):
    """Raised when a player attempts to play out of sequence."""
    pass


class GameSession(BaseModel):
    """Server-authoritative state for an in-chat multiplayer game."""

    id: str = Field(..., description="Unique game session ID")
    session_id: str = Field(..., description="Associated ChatSession ID")
    game_type: GameType = Field(default=GameType.TICTACTOE, description="Game type")
    player_x_id: str = Field(..., description="User ID playing as X (moves first)")
    player_o_id: str = Field(..., description="User ID playing as O")
    status: GameStatus = Field(default=GameStatus.IN_PROGRESS, description="Game status")
    current_turn_user_id: str = Field(..., description="ID of player whose turn it is")
    board: List[List[str]] = Field(
        default_factory=lambda: [["", "", ""], ["", "", ""], ["", "", ""]],
        description="3x3 grid representation",
    )
    winner_id: Optional[str] = None
    move_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def make_move(self, user_id: str, row: int, col: int) -> Tuple[GameStatus, Optional[str]]:
        """
        Validate and execute a move at (row, col) by player `user_id`.
        Returns (GameStatus, winner_id).
        """
        if self.status != GameStatus.IN_PROGRESS:
            raise InvalidMoveError("Game is already finished.")

        if user_id != self.current_turn_user_id:
            raise NotYourTurnError("It is not your turn.")

        if not (0 <= row <= 2 and 0 <= col <= 2):
            raise InvalidMoveError("Move out of board bounds.")

        if self.board[row][col] != "":
            raise InvalidMoveError("Cell is already occupied.")

        # Determine symbol
        symbol = "X" if user_id == self.player_x_id else "O"
        self.board[row][col] = symbol
        self.move_count += 1
        self.updated_at = datetime.now(timezone.utc)

        # Check for winner
        winning_symbol = self._check_winning_condition()
        if winning_symbol:
            self.status = GameStatus.COMPLETED
            self.winner_id = self.player_x_id if winning_symbol == "X" else self.player_o_id
            return self.status, self.winner_id

        # Check for draw
        if self.move_count >= 9:
            self.status = GameStatus.DRAW
            return self.status, None

        # Shift turn
        self.current_turn_user_id = (
            self.player_o_id if user_id == self.player_x_id else self.player_x_id
        )
        return self.status, None

    def _check_winning_condition(self) -> Optional[str]:
        """Check rows, columns, and diagonals for 3 matching symbols."""
        b = self.board
        # Rows
        for r in range(3):
            if b[r][0] and b[r][0] == b[r][1] == b[r][2]:
                return b[r][0]
        # Columns
        for c in range(3):
            if b[0][c] and b[0][c] == b[1][c] == b[2][c]:
                return b[0][c]
        # Diagonals
        if b[0][0] and b[0][0] == b[1][1] == b[2][2]:
            return b[0][0]
        if b[0][2] and b[0][2] == b[1][1] == b[2][0]:
            return b[0][2]
        return None

    def forfeit(self, forfeiting_user_id: str) -> None:
        """Forfeit game, declaring opponent the winner."""
        if self.status != GameStatus.IN_PROGRESS:
            return
        self.status = GameStatus.FORFEITED
        self.winner_id = (
            self.player_o_id if forfeiting_user_id == self.player_x_id else self.player_x_id
        )
        self.updated_at = datetime.now(timezone.utc)
