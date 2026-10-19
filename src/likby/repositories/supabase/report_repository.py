"""
likby.repositories.supabase.report_repository
Supabase REST implementation of ReportRepository with local fallback.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, List, Optional
from likby.domain.entities.report import Report
from likby.domain.enums import ReportCategory, ReportStatus
from likby.repositories.interfaces import ReportRepository

logger = logging.getLogger(__name__)


class SupabaseReportRepository(ReportRepository):
    """Supabase REST-backed implementation of ReportRepository."""

    def __init__(self, client: Any, local_fallback: Optional[ReportRepository] = None) -> None:
        self._client = client
        self._fallback = local_fallback

    async def save(self, report: Report) -> None:
        if self._fallback:
            try:
                await self._fallback.save(report)
            except Exception as exc:
                logger.warning("[SupabaseReportRepository] local fallback save error: %s", exc)

        payload = {
            "id": report.id,
            "session_id": report.session_id,
            "reporter_id": report.reporter_id,
            "reported_id": report.reported_id,
            "reason": report.category.value if hasattr(report.category, "value") else str(report.category),
            "details": report.reason or report.evidence_snippet or "",
            "status": report.status.value if hasattr(report.status, "value") else str(report.status),
            "created_at": report.created_at.isoformat() if report.created_at else datetime.now(timezone.utc).isoformat(),
        }

        try:
            await asyncio.to_thread(
                self._client.table("reports").upsert(payload).execute
            )
        except Exception as exc:
            logger.error("[SupabaseReportRepository] Failed to upsert report %s: %s", report.id, exc)

    async def get_by_id(self, report_id: str) -> Optional[Report]:
        try:
            res = await asyncio.to_thread(
                self._client.table("reports").select("*").eq("id", report_id).limit(1).execute
            )
            if res.data:
                return self._row_to_entity(res.data[0])
        except Exception as exc:
            logger.warning("[SupabaseReportRepository] get_by_id error: %s", exc)

        if self._fallback:
            return await self._fallback.get_by_id(report_id)
        return None

    async def get_by_reported_user_id(self, reported_id: str) -> List[Report]:
        try:
            res = await asyncio.to_thread(
                self._client.table("reports")
                .select("*")
                .eq("reported_id", reported_id)
                .order("created_at", desc=True)
                .execute
            )
            if res.data:
                return [self._row_to_entity(row) for row in res.data]
        except Exception as exc:
            logger.warning("[SupabaseReportRepository] get_by_reported_user_id error: %s", exc)

        if self._fallback:
            return await self._fallback.get_by_reported_user_id(reported_id)
        return []

    async def get_report_count_for_user(self, reported_id: str) -> int:
        reports = await self.get_by_reported_user_id(reported_id)
        return len(reports)

    def _row_to_entity(self, row: dict) -> Report:
        created_at = datetime.now(timezone.utc)
        if row.get("created_at"):
            created_at = datetime.fromisoformat(row["created_at"])

        cat_str = row.get("reason", "OTHER")
        try:
            cat = ReportCategory(cat_str)
        except Exception:
            cat = ReportCategory.OTHER

        return Report(
            id=row["id"],
            reporter_id=row["reporter_id"],
            reported_id=row["reported_id"],
            session_id=row.get("session_id"),
            category=cat,
            reason=row.get("details", ""),
            status=ReportStatus(row["status"]),
            created_at=created_at,
        )
