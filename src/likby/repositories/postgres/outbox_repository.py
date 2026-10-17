"""
likby.repositories.postgres.outbox_repository
asyncpg PostgreSQL / Supabase implementation of OutboxRepository.
Implements transactional job claiming using FOR UPDATE SKIP LOCKED.
"""

from datetime import datetime, timezone
import json
from typing import List, Optional
import asyncpg
from likby.domain.entities.outbox import OutboxJob
from likby.domain.enums import OutboxJobStatus
from likby.repositories.interfaces import OutboxRepository


class PostgresOutboxRepository(OutboxRepository):
    """PostgreSQL implementation of OutboxRepository for reliable cross-service delivery."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_id(self, job_id: str) -> Optional[OutboxJob]:
        query = """
            SELECT id, aggregate_id as session_id, payload->>'message_id' as message_id,
                   (payload->>'recipient_tg_id')::bigint as recipient_tg_id, status,
                   attempt_count, next_attempt_at, last_error, created_at, completed_at
            FROM outbox_jobs WHERE id = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, job_id)
            if not row:
                return None
            return self._row_to_entity(row)

    async def save(self, job: OutboxJob) -> None:
        query = """
            INSERT INTO outbox_jobs (
                id, event_type, aggregate_type, aggregate_id, idempotency_key,
                payload, status, attempt_count, next_attempt_at, last_error, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (idempotency_key) DO UPDATE SET
                status = EXCLUDED.status,
                attempt_count = EXCLUDED.attempt_count,
                next_attempt_at = EXCLUDED.next_attempt_at,
                last_error = EXCLUDED.last_error
        """
        idempotency_key = f"{job.session_id}_{job.message_id}_{job.recipient_tg_id}"
        payload_dict = {
            "session_id": job.session_id,
            "message_id": job.message_id,
            "recipient_tg_id": job.recipient_tg_id,
        }
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                job.id,
                "telegram.deliver_message",
                "chat_session",
                job.session_id,
                idempotency_key,
                json.dumps(payload_dict),
                job.status.value,
                job.attempt_count,
                job.next_attempt_at,
                job.last_error,
                job.created_at,
            )

    async def claim_pending_jobs(self, batch_size: int = 10) -> List[OutboxJob]:
        """Claim pending jobs atomically using FOR UPDATE SKIP LOCKED."""
        select_query = """
            SELECT id, aggregate_id as session_id, payload->>'message_id' as message_id,
                   (payload->>'recipient_tg_id')::bigint as recipient_tg_id, status,
                   attempt_count, next_attempt_at, last_error, created_at, completed_at
            FROM outbox_jobs
            WHERE status IN ('PENDING', 'FAILED')
              AND next_attempt_at <= NOW()
              AND (locked_at IS NULL OR locked_at < NOW() - INTERVAL '60 seconds')
            ORDER BY next_attempt_at ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        """
        update_query = """
            UPDATE outbox_jobs
            SET status = 'PROCESSING', locked_at = NOW(), attempt_count = attempt_count + 1
            WHERE id = ANY($1::text[])
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(select_query, batch_size)
                if not rows:
                    return []
                job_ids = [r["id"] for r in rows]
                await conn.execute(update_query, job_ids)
                return [self._row_to_entity(r) for r in rows]

    async def mark_completed(self, job_id: str) -> None:
        query = """
            UPDATE outbox_jobs
            SET status = 'COMPLETED', completed_at = NOW(), locked_at = NULL
            WHERE id = $1
        """
        async with self._pool.acquire() as conn:
            await conn.execute(query, job_id)

    async def mark_failed(
        self,
        job_id: str,
        error: str,
        next_attempt_at: Optional[datetime] = None,
    ) -> None:
        query = """
            UPDATE outbox_jobs
            SET status = 'FAILED', last_error = $2, next_attempt_at = $3, locked_at = NULL
            WHERE id = $1
        """
        async with self._pool.acquire() as conn:
            await conn.execute(query, job_id, error, next_attempt_at or datetime.now(timezone.utc))

    def _row_to_entity(self, row: asyncpg.Record) -> OutboxJob:
        return OutboxJob(
            id=row["id"],
            session_id=row["session_id"],
            message_id=row["message_id"],
            recipient_tg_id=row["recipient_tg_id"],
            status=OutboxJobStatus(row["status"]) if row["status"] in OutboxJobStatus.__members__.values() else OutboxJobStatus.PENDING,
            attempt_count=row["attempt_count"],
            next_attempt_at=row["next_attempt_at"],
            last_error=row["last_error"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )
