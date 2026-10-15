"""
tikible.repositories.sqlite.report_repository
aiosqlite implementation of ReportRepository.
"""

from datetime import datetime
import aiosqlite
from tikible.domain.entities.report import Report
from tikible.domain.enums import ReportCategory, ReportStatus
from tikible.repositories.interfaces import ReportRepository


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

    async def get_report_count_for_user(self, reported_id: str) -> int:
        async with self._conn.execute(
            "SELECT COUNT(*) FROM reports WHERE reported_id = ?",
            (reported_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
