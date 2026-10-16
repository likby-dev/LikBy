"""
likby.repositories.sqlite.rating_repository
aiosqlite implementation of RatingRepository.
"""

from datetime import datetime
from typing import Optional
import aiosqlite
from likby.domain.entities.rating import SessionRating
from likby.domain.enums import RatingType
from likby.repositories.interfaces import RatingRepository


class SqliteRatingRepository(RatingRepository):
    """SQLite implementation of RatingRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, rating: SessionRating) -> None:
        await self._conn.execute(
            """
            INSERT INTO session_ratings (id, session_id, rater_id, ratee_id, rating, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, rater_id) DO UPDATE SET
                rating = excluded.rating
            """,
            (
                rating.id,
                rating.session_id,
                rating.rater_id,
                rating.ratee_id,
                rating.rating.value,
                rating.created_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_by_session_and_rater(self, session_id: str, rater_id: str) -> Optional[SessionRating]:
        async with self._conn.execute(
            """
            SELECT id, session_id, rater_id, ratee_id, rating, created_at
            FROM session_ratings
            WHERE session_id = ? AND rater_id = ?
            """,
            (session_id, rater_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    def _row_to_entity(self, row: tuple) -> SessionRating:
        return SessionRating(
            id=row[0],
            session_id=row[1],
            rater_id=row[2],
            ratee_id=row[3],
            rating=RatingType(row[4]),
            created_at=datetime.fromisoformat(row[5]),
        )
