"""
tikible.repositories.sqlite.match_ticket_repository
aiosqlite implementation of MatchTicketRepository.
"""

from datetime import datetime
import json
from typing import List, Optional
import aiosqlite
from tikible.domain.entities.match_ticket import MatchTicket
from tikible.domain.enums import Gender, GenderPreference, TicketStatus
from tikible.repositories.interfaces import MatchTicketRepository


class SqliteMatchTicketRepository(MatchTicketRepository):
    """SQLite implementation of MatchTicketRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def get_by_id(self, ticket_id: str) -> Optional[MatchTicket]:
        async with self._conn.execute(
            """
            SELECT id, user_id, user_gender, user_age, languages, interests,
                   preferred_genders, min_age, max_age, status, created_at,
                   expires_at, matched_at, matched_user_id, session_id, lock_version
            FROM match_tickets WHERE id = ?
            """,
            (ticket_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_active_by_user_id(self, user_id: str) -> Optional[MatchTicket]:
        async with self._conn.execute(
            """
            SELECT id, user_id, user_gender, user_age, languages, interests,
                   preferred_genders, min_age, max_age, status, created_at,
                   expires_at, matched_at, matched_user_id, session_id, lock_version
            FROM match_tickets WHERE user_id = ? AND status = 'WAITING'
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_waiting_tickets(self, limit: int = 50) -> List[MatchTicket]:
        async with self._conn.execute(
            """
            SELECT id, user_id, user_gender, user_age, languages, interests,
                   preferred_genders, min_age, max_age, status, created_at,
                   expires_at, matched_at, matched_user_id, session_id, lock_version
            FROM match_tickets WHERE status = 'WAITING'
            ORDER BY created_at ASC LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_entity(r) for r in rows]

    async def save(self, ticket: MatchTicket) -> None:
        await self._conn.execute(
            """
            INSERT INTO match_tickets (
                id, user_id, user_gender, user_age, languages, interests,
                preferred_genders, min_age, max_age, status, created_at,
                expires_at, matched_at, matched_user_id, session_id, lock_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                matched_at = excluded.matched_at,
                matched_user_id = excluded.matched_user_id,
                session_id = excluded.session_id,
                lock_version = excluded.lock_version
            """,
            (
                ticket.id,
                ticket.user_id,
                ticket.user_gender.value,
                ticket.user_age,
                json.dumps(ticket.languages),
                json.dumps(ticket.interests),
                json.dumps([g.value for g in ticket.preferred_genders]),
                ticket.min_age,
                ticket.max_age,
                ticket.status.value,
                ticket.created_at.isoformat(),
                ticket.expires_at.isoformat(),
                ticket.matched_at.isoformat() if ticket.matched_at else None,
                ticket.matched_user_id,
                ticket.session_id,
                ticket.lock_version,
            ),
        )
        await self._conn.commit()

    def _row_to_entity(self, row: tuple) -> MatchTicket:
        return MatchTicket(
            id=row[0],
            user_id=row[1],
            user_gender=Gender(row[2]),
            user_age=row[3],
            languages=json.loads(row[4]),
            interests=json.loads(row[5]),
            preferred_genders=[GenderPreference(p) for p in json.loads(row[6])],
            min_age=row[7],
            max_age=row[8],
            status=TicketStatus(row[9]),
            created_at=datetime.fromisoformat(row[10]),
            expires_at=datetime.fromisoformat(row[11]),
            matched_at=datetime.fromisoformat(row[12]) if row[12] else None,
            matched_user_id=row[13],
            session_id=row[14],
            lock_version=row[15],
        )
