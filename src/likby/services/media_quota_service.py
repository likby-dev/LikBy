"""
likby.services.media_quota_service
Centralized quota enforcement for media uploads and receipts.
Subscription-aware, concurrency-safe, UTC-aligned, and idempotent.
Zero advertisements, no self-destructing media.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any
import uuid

from likby.domain.entities.media_quota import MediaQuotaEvent
from likby.domain.enums import MediaQuotaStatus, QuotaOperationType
from likby.repositories.interfaces import DailyUsageRepository, MediaQuotaEventRepository
from likby.services.subscription_service import SubscriptionService


class MediaQuotaService:
    """
    Authoritative service governing media quotas across all subscription tiers:
    - Base: 20 uploads / 10 receives per UTC day
    - Spark: 40 uploads / 20 receives per UTC day
    - Premium: 100 uploads / 50 receives per UTC day
    - Diamond: 250 uploads / 100 receives per UTC day
    """

    def __init__(
        self,
        daily_usage_repo: DailyUsageRepository,
        quota_event_repo: MediaQuotaEventRepository,
        subscription_service: SubscriptionService,
    ) -> None:
        self._daily_usage_repo = daily_usage_repo
        self._quota_event_repo = quota_event_repo
        self._sub_service = subscription_service

    @staticmethod
    def get_current_utc_date() -> str:
        """Returns YYYY-MM-DD in UTC calendar day."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @staticmethod
    def get_next_reset_utc() -> datetime:
        """Returns the upcoming 00:00:00 UTC timestamp."""
        now_utc = datetime.now(timezone.utc)
        tomorrow_utc = (now_utc + timedelta(days=1)).date()
        return datetime(tomorrow_utc.year, tomorrow_utc.month, tomorrow_utc.day, 0, 0, 0, tzinfo=timezone.utc)

    @staticmethod
    def format_reset_time_str() -> str:
        """Returns human-friendly string e.g. '00:00 UTC'."""
        return "00:00 UTC"

    async def get_user_media_limits(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch authoritative limits from subscription service.
        Returns: {
            "tier": str,
            "display_name": str,
            "upload_limit": int,
            "receive_limit": int,
            "max_image_size_bytes": int,
            "max_video_size_bytes": int
        }
        """
        plan_limits = await self._sub_service.get_plan_limits(user_id)
        return {
            "tier": plan_limits.get("tier", "BASE"),
            "display_name": plan_limits.get("display_name", "LikBy Base"),
            "upload_limit": plan_limits.get("daily_uploads_limit", 20),
            "receive_limit": plan_limits.get("daily_receive_limit", 10),
            "max_image_size_bytes": plan_limits.get("max_image_size_bytes", 20 * 1024 * 1024),
            "max_video_size_bytes": plan_limits.get("max_video_size_bytes", 20 * 1024 * 1024),
        }

    async def check_upload_quota(
        self,
        user_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[bool, int, int, str]:
        """
        Check if user has upload quota available for today (UTC).
        If idempotency_key is provided and already COMMITTED/RESERVED for this key, allow without consuming extra.
        Returns: (allowed, used_count, limit, rejection_reason_or_empty)
        """
        if idempotency_key:
            existing = await self._quota_event_repo.get_by_idempotency_key(idempotency_key)
            if existing and existing.status in (MediaQuotaStatus.COMMITTED, MediaQuotaStatus.RESERVED):
                limits = await self.get_user_media_limits(user_id)
                usage_date = self.get_current_utc_date()
                usage = await self._daily_usage_repo.get_or_create(user_id, usage_date)
                return True, usage.uploads_count, limits["upload_limit"], ""

        limits = await self.get_user_media_limits(user_id)
        upload_limit = limits["upload_limit"]
        usage_date = self.get_current_utc_date()
        usage = await self._daily_usage_repo.get_or_create(user_id, usage_date)

        if usage.uploads_count >= upload_limit:
            return False, usage.uploads_count, upload_limit, self.format_upload_quota_exceeded_msg(
                plan_name=limits["display_name"],
                used=usage.uploads_count,
                limit=upload_limit,
            )

        return True, usage.uploads_count, upload_limit, ""

    async def reserve_and_commit_upload(
        self,
        user_id: str,
        media_file_id: Optional[str],
        idempotency_key: str,
    ) -> Tuple[bool, int, int, str]:
        """
        Atomically reserve and increment upload quota unit.
        Guarantees idempotency on duplicate update.
        """
        # 1. Check idempotency first
        existing = await self._quota_event_repo.get_by_idempotency_key(idempotency_key)
        if existing:
            limits = await self.get_user_media_limits(user_id)
            usage_date = self.get_current_utc_date()
            usage = await self._daily_usage_repo.get_or_create(user_id, usage_date)
            return True, usage.uploads_count, limits["upload_limit"], ""

        # 2. Check quota
        allowed, used, limit, reason = await self.check_upload_quota(user_id, idempotency_key=None)
        if not allowed:
            return False, used, limit, reason

        # 3. Record event
        now = datetime.now(timezone.utc)
        event = MediaQuotaEvent(
            id=str(uuid.uuid4()),
            user_id=user_id,
            media_file_id=media_file_id,
            operation_type=QuotaOperationType.UPLOAD,
            idempotency_key=idempotency_key,
            status=MediaQuotaStatus.COMMITTED,
            created_at=now,
            completed_at=now,
        )
        inserted = await self._quota_event_repo.record_event(event)
        if not inserted:
            limits = await self.get_user_media_limits(user_id)
            usage_date = self.get_current_utc_date()
            usage = await self._daily_usage_repo.get_or_create(user_id, usage_date)
            return True, usage.uploads_count, limits["upload_limit"], ""

        # 4. Increment usage counter
        usage_date = self.get_current_utc_date()
        new_used = await self._daily_usage_repo.increment_upload(user_id, usage_date)
        return True, new_used, limit, ""

    async def check_receive_quota(
        self,
        recipient_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[bool, int, int, str]:
        """
        Check if recipient has receive quota available for today (UTC).
        Returns: (allowed, used_count, limit, rejection_reason_or_empty)
        """
        if idempotency_key:
            existing = await self._quota_event_repo.get_by_idempotency_key(idempotency_key)
            if existing and existing.status in (MediaQuotaStatus.COMMITTED, MediaQuotaStatus.RESERVED):
                limits = await self.get_user_media_limits(recipient_id)
                usage_date = self.get_current_utc_date()
                usage = await self._daily_usage_repo.get_or_create(recipient_id, usage_date)
                return True, usage.received_count, limits["receive_limit"], ""

        limits = await self.get_user_media_limits(recipient_id)
        receive_limit = limits["receive_limit"]
        usage_date = self.get_current_utc_date()
        usage = await self._daily_usage_repo.get_or_create(recipient_id, usage_date)

        if usage.received_count >= receive_limit:
            return False, usage.received_count, receive_limit, self.format_receive_quota_exceeded_msg(
                plan_name=limits["display_name"],
                used=usage.received_count,
                limit=receive_limit,
            )

        return True, usage.received_count, receive_limit, ""

    async def reserve_receive_quota(
        self,
        recipient_id: str,
        media_file_id: Optional[str],
        idempotency_key: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Pre-reserves a receive quota unit before external Telegram delivery attempt.
        Returns: (allowed, rejection_reason_if_not_allowed)
        """
        existing = await self._quota_event_repo.get_by_idempotency_key(idempotency_key)
        if existing:
            return True, None

        allowed, used, limit, reason = await self.check_receive_quota(recipient_id, idempotency_key=None)
        if not allowed:
            return False, reason

        event = MediaQuotaEvent(
            id=str(uuid.uuid4()),
            user_id=recipient_id,
            media_file_id=media_file_id,
            operation_type=QuotaOperationType.RECEIVE,
            idempotency_key=idempotency_key,
            status=MediaQuotaStatus.RESERVED,
            created_at=datetime.now(timezone.utc),
            completed_at=None,
        )
        await self._quota_event_repo.record_event(event)
        return True, None

    async def commit_receive_quota(
        self,
        recipient_id: str,
        idempotency_key: str,
    ) -> int:
        """
        Called ONLY after successful verified Telegram delivery.
        Atomically updates reservation to COMMITTED and increments recipient's daily received count.
        """
        now = datetime.now(timezone.utc)
        await self._quota_event_repo.update_status(
            idempotency_key=idempotency_key,
            status=MediaQuotaStatus.COMMITTED,
            completed_at=now,
        )
        usage_date = self.get_current_utc_date()
        return await self._daily_usage_repo.increment_received(recipient_id, usage_date)

    async def rollback_receive_quota(
        self,
        recipient_id: str,
        idempotency_key: str,
    ) -> None:
        """
        Called if Telegram delivery fails. Rolls back reservation so recipient is never charged for failed delivery.
        """
        await self._quota_event_repo.update_status(
            idempotency_key=idempotency_key,
            status=MediaQuotaStatus.ROLLED_BACK,
            completed_at=datetime.now(timezone.utc),
        )

    async def get_user_media_usage_summary(self, user_id: str) -> Dict[str, Any]:
        """Comprehensive media usage overview for /my_media_usage command."""
        limits = await self.get_user_media_limits(user_id)
        usage_date = self.get_current_utc_date()
        usage = await self._daily_usage_repo.get_or_create(user_id, usage_date)
        next_reset = self.get_next_reset_utc()

        uploads_used = usage.uploads_count
        uploads_limit = limits["upload_limit"]
        uploads_rem = max(0, uploads_limit - uploads_used)

        rec_used = usage.received_count
        rec_limit = limits["receive_limit"]
        rec_rem = max(0, rec_limit - rec_used)

        max_img_mb = limits["max_image_size_bytes"] // (1024 * 1024)
        max_vid_mb = limits["max_video_size_bytes"] // (1024 * 1024)

        return {
            "tier": limits["tier"],
            "plan_name": limits["display_name"],
            "uploads_used": uploads_used,
            "uploads_limit": uploads_limit,
            "uploads_remaining": uploads_rem,
            "received_used": rec_used,
            "received_limit": rec_limit,
            "received_remaining": rec_rem,
            "max_image_mb": max_img_mb,
            "max_video_mb": max_vid_mb,
            "next_reset_utc": next_reset.isoformat(),
        }

    @staticmethod
    def format_upload_quota_exceeded_msg(plan_name: str, used: int, limit: int) -> str:
        return (
            f"💜 You've reached today's media upload limit.\n\n"
            f"Your plan: {plan_name}\n"
            f"Uploads used: {used}/{limit}\n\n"
            f"Your upload allowance resets at the next daily reset (00:00 UTC).\n\n"
            f"Explore LikBy subscription options with /subscribe to increase your daily allowance."
        )

    @staticmethod
    def format_receive_quota_exceeded_msg(plan_name: str, used: int, limit: int) -> str:
        return (
            f"💜 You've reached today's media receiving limit.\n\n"
            f"Your plan: {plan_name}\n"
            f"Media received: {used}/{limit}\n\n"
            f"You can receive more media when your allowance resets (00:00 UTC) or when a higher entitlement becomes active."
        )
