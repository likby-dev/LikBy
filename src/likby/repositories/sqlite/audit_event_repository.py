"""
likby.repositories.sqlite.audit_event_repository
aiosqlite implementation of AuditEventRepository.
"""

from datetime import datetime
import json
from typing import List
import aiosqlite
from likby.domain.entities.payment import AuditEvent
from likby.repositories.interfaces import AuditEventRepository


class SqliteAuditEventRepository(AuditEventRepository):
    """SQLite append-only audit event logging repository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def record_event(self, event: AuditEvent) -> None:
        await self._conn.execute(
            """
            INSERT INTO audit_events (
                id, actor_id, event_type, entity_type, entity_id, timestamp, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.actor_id,
                event.event_type,
                event.entity_type,
                event.entity_id,
                event.timestamp.isoformat(),
                json.dumps(event.metadata_json),
            ),
        )
        await self._conn.commit()

    async def get_events_for_entity(self, entity_type: str, entity_id: str) -> List[AuditEvent]:
        events = []
        async with self._conn.execute(
            "SELECT id, actor_id, event_type, entity_type, entity_id, timestamp, metadata_json "
            "FROM audit_events WHERE entity_type = ? AND entity_id = ? ORDER BY timestamp DESC",
            (entity_type, entity_id),
        ) as cursor:
            async for row in cursor:
                events.append(
                    AuditEvent(
                        id=row[0],
                        actor_id=row[1],
                        event_type=row[2],
                        entity_type=row[3],
                        entity_id=row[4],
                        timestamp=datetime.fromisoformat(row[5]),
                        metadata_json=json.loads(row[6]) if row[6] else {},
                    )
                )
        return events
