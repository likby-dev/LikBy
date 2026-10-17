"""
likby.repositories.sqlite.media_quota_repository
aiosqlite implementation of MediaQuotaEventRepository for idempotent media quota auditing.
"""

from datetime import datetime, timezone
from typing import List, Optional
import aiosqlite

from likby.domain.entities.media_quota import MediaQuotaEvent
from likby.domain.enums import MediaQuotaStatus, QuotaOperationType
from likby.repositories.interfaces import MediaQuotaEventRepository


class SqliteMediaQuotaEventRepository(MediaQuotaEventRepository):
    """SQLite implementation of MediaQuotaEventRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def record_event(self, event: MediaQuotaEvent) -> bool:
        """
        Record a quota event with unique idempotency_key constraint.
        Returns True if newly inserted, False if event already exists.
        """
        created_str = event.created_at.isoformat()
        completed_str = event.completed_at.isoformat() if event.completed_at else None
        try:
            await self._conn.execute(
                """
                INSERT INTO media_quota_events (
                    id, user_id, media_file_id, operation_type, idempotency_key, status, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.user_id,
                    event.media_file_id,
                    event.operation_type.value,
                    event.idempotency_key,
                    event.status.value,
                    created_str,
                    completed_str,
                ),
            )
            await self._conn.commit()
            return True
        except aiosqlite.IntegrityError:
            # Duplicate idempotency key
            return False

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[MediaQuotaEvent]:
        async with self._conn.execute(
            """
            SELECT id, user_id, media_file_id, operation_type, idempotency_key, status, created_at, completed_at
            FROM media_quota_events WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return MediaQuotaEvent(
                id=row[0],
                user_id=row[1],
                media_file_id=row[2],
                operation_type=QuotaOperationType(row[3]),
                idempotency_key=row[4],
                status=MediaQuotaStatus(row[5]),
                created_at=datetime.fromisoformat(row[6]),
                completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
            )

    async def get_user_events_today(self, user_id: str, date_str: str) -> List[MediaQuotaEvent]:
        events = []
        async with self._conn.execute(
            """
            SELECT id, user_id, media_file_id, operation_type, idempotency_key, status, created_at, completed_at
            FROM media_quota_events WHERE user_id = ? AND created_at LIKE ?
            ORDER BY created_at ASC
            """,
            (user_id, f"{date_str}%"),
        ) as cursor:
            async for row in cursor:
                events.append(
                    MediaQuotaEvent(
                        id=row[0],
                        user_id=row[1],
                        media_file_id=row[2],
                        operation_type=QuotaOperationType(row[3]),
                        idempotency_key=row[4],
                        status=MediaQuotaStatus(row[5]),
                        created_at=datetime.fromisoformat(row[6]),
                        completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
                    )
                )
        return events

    async def update_status(
        self,
        idempotency_key: str,
        status: MediaQuotaStatus,
        completed_at: Optional[datetime] = None,
    ) -> bool:
        completed_str = completed_at.isoformat() if completed_at else None
        cursor = await self._conn.execute(
            """
            UPDATE media_quota_events
            SET status = ?, completed_at = ?
            WHERE idempotency_key = ?
            """,
            (status.value, completed_str, idempotency_key),
        )
        await self._conn.commit()
        return cursor.rowcount > 0
