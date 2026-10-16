"""
likby.repositories.sqlite.report_repository
aiosqlite implementation of ReportRepository.
"""

from datetime import datetime
from typing import List, Optional
import aiosqlite
from likby.domain.entities.report import Report
from likby.domain.enums import ReportCategory, ReportStatus
from likby.repositories.interfaces import ReportRepository


class SqliteReportRepository(ReportRepository):
    """SQLite implementation of ReportRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, report: Report) -> None:
        await self._conn.execute(
            """
            INSERT INTO reports (
                id, reporter_id, reported_id, session_id, category,
                reason, evidence_snippet, status, created_at,
                resolved_at, resolved_by, action_taken
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                resolved_at = excluded.resolved_at,
                resolved_by = excluded.resolved_by,
                action_taken = excluded.action_taken
            """,
            (
                report.id,
                report.reporter_id,
                report.reported_id,
                report.session_id,
                report.category.value,
                report.reason,
                report.evidence_snippet,
                report.status.value,
                report.created_at.isoformat(),
                report.resolved_at.isoformat() if report.resolved_at else None,
                report.resolved_by,
                report.action_taken,
            ),
        )
        await self._conn.commit()

    async def get_by_id(self, report_id: str) -> Optional[Report]:
        async with self._conn.execute(
            """
            SELECT id, reporter_id, reported_id, session_id, category,
                   reason, evidence_snippet, status, created_at,
                   resolved_at, resolved_by, action_taken
            FROM reports WHERE id = ?
            """,
            (report_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_by_reported_user_id(self, reported_id: str) -> List[Report]:
        async with self._conn.execute(
            """
            SELECT id, reporter_id, reported_id, session_id, category,
                   reason, evidence_snippet, status, created_at,
                   resolved_at, resolved_by, action_taken
            FROM reports WHERE reported_id = ?
            ORDER BY created_at DESC
            """,
            (reported_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_entity(r) for r in rows]

    async def get_report_count_for_user(self, reported_id: str) -> int:
        async with self._conn.execute(
            "SELECT COUNT(*) FROM reports WHERE reported_id = ?",
            (reported_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    def _row_to_entity(self, row: tuple) -> Report:
        return Report(
            id=row[0],
            reporter_id=row[1],
            reported_id=row[2],
            session_id=row[3],
            category=ReportCategory(row[4]),
            reason=row[5],
            evidence_snippet=row[6],
            status=ReportStatus(row[7]),
            created_at=datetime.fromisoformat(row[8]),
            resolved_at=datetime.fromisoformat(row[9]) if row[9] else None,
            resolved_by=row[10],
            action_taken=row[11],
        )
