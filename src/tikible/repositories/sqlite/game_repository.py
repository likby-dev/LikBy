"""
tikible.repositories.sqlite.game_repository
aiosqlite implementation of GameRepository.
"""

from datetime import datetime
import json
from typing import Optional
import aiosqlite
from tikible.domain.entities.game import GameSession
from tikible.domain.enums import GameStatus, GameType
from tikible.repositories.interfaces import GameRepository


class SqliteGameRepository(GameRepository):
    """SQLite implementation of GameRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def get_by_id(self, game_id: str) -> Optional[GameSession]:
        async with self._conn.execute(
            """
            SELECT id, session_id, game_type, player_x_id, player_o_id,
                   status, current_turn_user_id, board, winner_id,
                   move_count, created_at, updated_at
            FROM games WHERE id = ?
            """,
            (game_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_active_by_session_id(self, session_id: str) -> Optional[GameSession]:
        async with self._conn.execute(
            """
            SELECT id, session_id, game_type, player_x_id, player_o_id,
                   status, current_turn_user_id, board, winner_id,
                   move_count, created_at, updated_at
            FROM games WHERE session_id = ? AND status = 'IN_PROGRESS'
            ORDER BY created_at DESC LIMIT 1
            """,
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def save(self, game: GameSession) -> None:
        await self._conn.execute(
            """
            INSERT INTO games (
                id, session_id, game_type, player_x_id, player_o_id,
                status, current_turn_user_id, board, winner_id,
                move_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                current_turn_user_id = excluded.current_turn_user_id,
                board = excluded.board,
                winner_id = excluded.winner_id,
                move_count = excluded.move_count,
                updated_at = excluded.updated_at
            """,
            (
                game.id,
                game.session_id,
                game.game_type.value,
                game.player_x_id,
                game.player_o_id,
                game.status.value,
                game.current_turn_user_id,
                json.dumps(game.board),
                game.winner_id,
                game.move_count,
                game.created_at.isoformat(),
                game.updated_at.isoformat(),
            ),
        )
        await self._conn.commit()

    def _row_to_entity(self, row: tuple) -> GameSession:
        return GameSession(
            id=row[0],
            session_id=row[1],
            game_type=GameType(row[2]),
            player_x_id=row[3],
            player_o_id=row[4],
            status=GameStatus(row[5]),
            current_turn_user_id=row[6],
            board=json.loads(row[7]),
            winner_id=row[8],
            move_count=row[9],
            created_at=datetime.fromisoformat(row[10]),
            updated_at=datetime.fromisoformat(row[11]),
        )
