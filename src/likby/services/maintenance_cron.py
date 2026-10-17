"""
likby.services.maintenance_cron
Unified maintenance and cron orchestration service.
Executes scheduled background routines:
- Reaping expired matchmaking tickets
- Reaping abandoned/inactive chat sessions
- Reconciling expired subscription entitlements (e.g., 24h Spark passes)
- Reconciling expired connection requests
- Processing pending transactional outbox jobs
- Tracking execution telemetry, health, and status for /health/ready and cron triggers
"""

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Dict, Optional
import structlog

logger = structlog.get_logger(__name__)


class MaintenanceCronService:
    """Orchestrates scheduled maintenance cron jobs and reports execution telemetry."""

    def __init__(
        self,
        ticket_repo=None,
        session_repo=None,
        subscription_repo=None,
        connection_request_repo=None,
        reconciliation_service=None,
        outbox_worker=None,
    ) -> None:
        self.ticket_repo = ticket_repo
        self.session_repo = session_repo
        self.subscription_repo = subscription_repo
        self.connection_request_repo = connection_request_repo
        self.reconciliation_service = reconciliation_service
        self.outbox_worker = outbox_worker

        self.runs_count: int = 0
        self.last_run: Optional[datetime] = None
        self.last_duration_ms: float = 0.0
        self.last_status: str = "initialized"
        self.last_results: Dict[str, Any] = {}
        self.last_error: Optional[str] = None
        self._is_running: bool = False

    async def run_maintenance_cycle(self) -> Dict[str, Any]:
        """Execute a full maintenance and reconciliation cycle."""
        for _ in range(25):
            if not self._is_running:
                break
            await asyncio.sleep(0.1)

        if self._is_running:
            return {
                "status": "in_progress",
                "note": "Cycle already executing",
                "tickets_reaped": 0,
                "sessions_reaped": 0,
                "subscriptions_reconciled": 0,
                "requests_reaped": 0,
                "outbox_jobs_processed": 0,
                "stuck_jobs_reconciled": 0,
            }

        self._is_running = True
        try:
            start_time = time.perf_counter()
            now = datetime.now(timezone.utc)
            results = {
                "timestamp": now.isoformat(),
                "tickets_reaped": 0,
                "sessions_reaped": 0,
                "subscriptions_reconciled": 0,
                "requests_reaped": 0,
                "outbox_jobs_processed": 0,
                "stuck_jobs_reconciled": 0,
            }

            try:
                # 1. Reap expired match tickets
                if self.ticket_repo and hasattr(self.ticket_repo, "reap_expired_tickets"):
                    try:
                        results["tickets_reaped"] = await self.ticket_repo.reap_expired_tickets(now=now)
                    except Exception as exc:
                        logger.warning("Ticket reaper error", error=str(exc))

                # 2. Reap inactive chat sessions (inactive > 24 hours)
                if self.session_repo and hasattr(self.session_repo, "reap_inactive_sessions"):
                    try:
                        results["sessions_reaped"] = await self.session_repo.reap_inactive_sessions(cutoff_hours=24)
                    except Exception as exc:
                        logger.warning("Session reaper error", error=str(exc))

                # 3. Reconcile expired subscriptions
                if self.subscription_repo and hasattr(self.subscription_repo, "reap_expired_subscriptions"):
                    try:
                        results["subscriptions_reconciled"] = await self.subscription_repo.reap_expired_subscriptions(now=now)
                    except Exception as exc:
                        logger.warning("Subscription reaper error", error=str(exc))

                # 4. Reap expired connection requests (older than 7 days)
                if self.connection_request_repo and hasattr(self.connection_request_repo, "reap_expired_requests"):
                    try:
                        results["requests_reaped"] = await self.connection_request_repo.reap_expired_requests(days=7)
                    except Exception as exc:
                        logger.warning("Connection request reaper error", error=str(exc))

                # 5. Reconcile stuck outbox jobs
                if self.reconciliation_service and hasattr(self.reconciliation_service, "reconcile_stuck_outbox_jobs"):
                    try:
                        results["stuck_jobs_reconciled"] = await self.reconciliation_service.reconcile_stuck_outbox_jobs()
                    except Exception as exc:
                        logger.warning("Stuck outbox reconciliation error", error=str(exc))

                # 6. Process outbox batch if worker attached
                if self.outbox_worker and hasattr(self.outbox_worker, "process_batch"):
                    try:
                        results["outbox_jobs_processed"] = await self.outbox_worker.process_batch()
                    except Exception as exc:
                        logger.warning("Outbox worker batch error", error=str(exc))

                duration = (time.perf_counter() - start_time) * 1000.0
                self.last_duration_ms = round(duration, 2)
                self.runs_count += 1
                self.last_run = now
                self.last_status = "healthy"
                self.last_results = results
                self.last_error = None

                logger.info(
                    "Maintenance cron cycle completed",
                    duration_ms=self.last_duration_ms,
                    runs_count=self.runs_count,
                    results=results,
                )
                return results

            except Exception as exc:
                duration = (time.perf_counter() - start_time) * 1000.0
                self.last_duration_ms = round(duration, 2)
                self.last_status = "error"
                self.last_error = str(exc)
                logger.error("Maintenance cron cycle failed", error=str(exc), duration_ms=self.last_duration_ms)
                return {
                    "timestamp": now.isoformat(),
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": self.last_duration_ms,
                }
        finally:
            self._is_running = False

    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic status for health checks and monitoring."""
        return {
            "status": self.last_status,
            "runs_total": self.runs_count,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_duration_ms": self.last_duration_ms,
            "last_error": self.last_error,
            "last_results": self.last_results,
        }
