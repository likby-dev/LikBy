"""
likby.repositories.sqlite.connection_request_repository
aiosqlite implementation of ConnectionRequestRepository.
"""

from datetime import datetime
from typing import List, Optional
import aiosqlite
from likby.domain.entities.connection_request import ConnectionRequest
from likby.domain.enums import ConnectionRequestStatus
from likby.repositories.interfaces import ConnectionRequestRepository


class SqliteConnectionRequestRepository(ConnectionRequestRepository):
    """SQLite implementation of ConnectionRequestRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, request: ConnectionRequest) -> None:
        await self._conn.execute(
            """
            INSERT INTO connection_requests (id, sender_id, target_id, status, created_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                resolved_at = excluded.resolved_at
            """,
            (
                request.id,
                request.sender_id,
                request.target_id,
                request.status.value,
                request.created_at.isoformat(),
                request.resolved_at.isoformat() if request.resolved_at else None,
            ),
        )
        await self._conn.commit()

    async def get_by_id(self, request_id: str) -> Optional[ConnectionRequest]:
        async with self._conn.execute(
            """
            SELECT id, sender_id, target_id, status, created_at, resolved_at
            FROM connection_requests WHERE id = ?
            """,
            (request_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_pending_between(self, sender_id: str, target_id: str) -> Optional[ConnectionRequest]:
        async with self._conn.execute(
            """
            SELECT id, sender_id, target_id, status, created_at, resolved_at
            FROM connection_requests
            WHERE sender_id = ? AND target_id = ? AND status = 'PENDING'
            """,
            (sender_id, target_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_incoming_requests(self, target_id: str) -> List[ConnectionRequest]:
        async with self._conn.execute(
            """
            SELECT id, sender_id, target_id, status, created_at, resolved_at
            FROM connection_requests
            WHERE target_id = ? AND status = 'PENDING'
            ORDER BY created_at DESC
            """,
            (target_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_entity(r) for r in rows]

    def _row_to_entity(self, row: tuple) -> ConnectionRequest:
        return ConnectionRequest(
            id=row[0],
            sender_id=row[1],
            target_id=row[2],
            status=ConnectionRequestStatus(row[3]),
            created_at=datetime.fromisoformat(row[4]),
            resolved_at=datetime.fromisoformat(row[5]) if row[5] else None,
        )
