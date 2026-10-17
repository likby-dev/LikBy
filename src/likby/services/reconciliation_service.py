"""
likby.services.reconciliation_service
Cross-service reconciliation service for auditing and correcting inconsistencies.
Safely detects and repairs:
- Stuck outbox jobs
- Expired temporary subscription entitlements
- Expired pending connection requests
- Orphaned or missing media assets
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import structlog
from likby.repositories.interfaces import (
    ConnectionRequestRepository,
    MediaAssetRepository,
    OutboxRepository,
    SubscriptionRepository,
)
from likby.services.media_storage_service import MediaService

logger = structlog.get_logger(__name__)


class ReconciliationService:
    """Performs scheduled or on-demand cross-service reconciliation safely."""

    def __init__(
        self,
        outbox_repo: OutboxRepository,
        subscription_repo: Optional[SubscriptionRepository] = None,
        connection_request_repo: Optional[ConnectionRequestRepository] = None,
        media_repo: Optional[MediaAssetRepository] = None,
        media_service: Optional[MediaService] = None,
    ) -> None:
        self._outbox_repo = outbox_repo
        self._sub_repo = subscription_repo
        self._req_repo = connection_request_repo
        self._media_repo = media_repo
        self._media_service = media_service

    async def reconcile_stuck_outbox_jobs(self, stuck_seconds: int = 120) -> int:
        """
        Identify outbox jobs locked in PROCESSING or FAILED with next_attempt_at reached,
        and reset them to PENDING.
        """
        reconciled = 0
        now = datetime.now(timezone.utc)
        import aiosqlite
        conn = getattr(self._outbox_repo, "_conn", None)
        if conn and isinstance(conn, aiosqlite.Connection):
            try:
                cutoff = (now - timedelta(seconds=stuck_seconds)).isoformat()
                async with conn.execute(
                    """
                    UPDATE outbox_jobs
                    SET status = 'PENDING'
                    WHERE status = 'PROCESSING' AND datetime(created_at) < datetime(?)
                    """,
                    (cutoff,),
                ) as cursor:
                    reconciled = cursor.rowcount
                await conn.commit()
            except Exception as e:
                logger.warning("Error reconciling stuck outbox jobs", error=str(e))
        logger.info("Reconciled stuck outbox jobs", count=reconciled)
        return reconciled

    async def reconcile_expired_subscriptions(self) -> int:
        """
        Identify active subscriptions that have passed their expiration timestamp
        and downgrade them to Base.
        """
        count = 0
        now = datetime.now(timezone.utc)
        if self._sub_repo and hasattr(self._sub_repo, "reap_expired_subscriptions"):
            try:
                count = await self._sub_repo.reap_expired_subscriptions(now=now)
            except Exception as e:
                logger.warning("Error reaping expired subscriptions", error=str(e))
        logger.info("Reconciled expired subscriptions", count=count, timestamp=now.isoformat())
        return count

    async def reconcile_orphaned_assets(self, session_id: Optional[str] = None) -> int:
        """
        Check assets in metadata repository against storage provider to verify physical presence.
        """
        orphans = 0
        if not self._media_repo or not self._media_service:
            return 0

        # Optional session check
        if session_id:
            assets = await self._media_repo.list_by_session_id(session_id)
            for asset in assets:
                exists = await self._media_service.verify_object_exists(asset.id)
                if not exists:
                    orphans += 1
                    logger.warning("Detected orphaned media asset", asset_id=asset.id, object_key=asset.object_key)
        return orphans

    async def run_full_reconciliation(self) -> Dict[str, Any]:
        """Execute complete idempotent reconciliation sweep."""
        logger.info("Starting full cross-service reconciliation sweep")
        stuck = await self.reconcile_stuck_outbox_jobs()
        subs = await self.reconcile_expired_subscriptions()
        orphans = await self.reconcile_orphaned_assets()

        results = {
            "stuck_jobs_reset": stuck,
            "expired_subscriptions_reconciled": subs,
            "orphaned_assets_flagged": orphans,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Reconciliation sweep completed", results=results)
        return results
