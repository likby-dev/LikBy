"""
likby.repositories.sqlite.karma_repository
aiosqlite implementation of KarmaRepository.
"""

from datetime import datetime
from typing import List
import aiosqlite
from likby.domain.entities.karma import KarmaLedgerEntry
from likby.domain.enums import KarmaSourceType
from likby.repositories.interfaces import KarmaRepository


class SqliteKarmaRepository(KarmaRepository):
    """SQLite implementation of KarmaRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save_entry(self, entry: KarmaLedgerEntry) -> bool:
        """Save a ledger entry idempotently. Returns True if saved, False if duplicate."""
        try:
            await self._conn.execute(
                """
                INSERT INTO karma_ledger (id, user_id, source_type, reference_id, delta, idempotency_key, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.user_id,
                    entry.source_type.value,
                    entry.reference_id,
                    entry.delta,
                    entry.idempotency_key,
                    entry.created_at.isoformat(),
                ),
            )
            await self._conn.commit()
            return True
        except aiosqlite.IntegrityError:
            # Duplicate idempotency_key
            return False

    async def get_user_ledger(self, user_id: str, limit: int = 20) -> List[KarmaLedgerEntry]:
        async with self._conn.execute(
            """
            SELECT id, user_id, source_type, reference_id, delta, idempotency_key, created_at
            FROM karma_ledger
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_entity(r) for r in rows]

    async def get_user_karma_score(self, user_id: str) -> int:
        async with self._conn.execute(
            """
            SELECT COALESCE(SUM(delta), 0) + 100
            FROM karma_ledger
            WHERE user_id = ?
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 100

    def _row_to_entity(self, row: tuple) -> KarmaLedgerEntry:
        return KarmaLedgerEntry(
            id=row[0],
            user_id=row[1],
            source_type=KarmaSourceType(row[2]),
            reference_id=row[3],
            delta=row[4],
            idempotency_key=row[5],
            created_at=datetime.fromisoformat(row[6]),
        )
