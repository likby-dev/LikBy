"""
likby.repositories.sqlite.outbox_repository
aiosqlite implementation of OutboxRepository.
"""

from datetime import datetime, timezone
from typing import List
import aiosqlite
from likby.domain.entities.outbox import OutboxJob
from likby.domain.enums import OutboxJobStatus
from likby.repositories.interfaces import OutboxRepository


class SqliteOutboxRepository(OutboxRepository):
    """SQLite implementation of OutboxRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, job: OutboxJob) -> None:
        await self._conn.execute(
            """
            INSERT INTO outbox_jobs (
                id, session_id, message_id, recipient_tg_id, status,
                attempts, max_attempts, last_error, next_attempt_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                attempts = excluded.attempts,
                last_error = excluded.last_error,
                next_attempt_at = excluded.next_attempt_at
            """,
            (
                job.id,
                job.session_id,
                job.message_id,
                job.recipient_tg_id,
                job.status.value,
                job.attempts,
                job.max_attempts,
                job.last_error,
                job.next_attempt_at.isoformat(),
                job.created_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_pending_jobs(self, limit: int = 20) -> List[OutboxJob]:
        now_str = datetime.now(timezone.utc).isoformat()
        async with self._conn.execute(
            """
            SELECT id, session_id, message_id, recipient_tg_id, status,
                   attempts, max_attempts, last_error, next_attempt_at, created_at
            FROM outbox_jobs
            WHERE status = 'PENDING' AND next_attempt_at <= ?
            ORDER BY next_attempt_at ASC
            LIMIT ?
            """,
            (now_str, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_entity(r) for r in rows]

    async def update_job(self, job: OutboxJob) -> None:
        await self.save(job)

    def _row_to_entity(self, row: tuple) -> OutboxJob:
        return OutboxJob(
            id=row[0],
            session_id=row[1],
            message_id=row[2],
            recipient_tg_id=row[3],
            status=OutboxJobStatus(row[4]),
            attempts=row[5],
            max_attempts=row[6],
            last_error=row[7],
            next_attempt_at=datetime.fromisoformat(row[8]),
            created_at=datetime.fromisoformat(row[9]),
        )
