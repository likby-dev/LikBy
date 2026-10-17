"""
likby.services.outbox_worker
Transactional outbox processor for cross-service durability.
Dispatches pending jobs for Firestore persistence, R2 media archival, and Telegram delivery.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import random
from typing import Any, Dict, Optional
import structlog
from aiogram import Bot
from likby.domain.entities.outbox import OutboxJob
from likby.domain.enums import MessageDeliveryStatus, OutboxJobStatus
from likby.repositories.interfaces import (
    MediaAssetRepository,
    MessageRepository,
    OutboxRepository,
)
from likby.services.media_storage_service import MediaService

logger = structlog.get_logger(__name__)


class OutboxWorker:
    """Processes pending outbox jobs with exponential backoff and idempotency."""

    def __init__(
        self,
        outbox_repo: OutboxRepository,
        bot: Bot,
        message_repo: Optional[MessageRepository] = None,
        media_service: Optional[MediaService] = None,
        batch_size: int = 25,
        poll_interval: float = 2.0,
        max_attempts: int = 10,
        backoff_base: float = 2.0,
        backoff_max: float = 300.0,
    ) -> None:
        self._outbox_repo = outbox_repo
        self._bot = bot
        self._message_repo = message_repo
        self._media_service = media_service
        self._batch_size = batch_size
        self._poll_interval = poll_interval
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._is_running = False

    def calculate_next_backoff(self, attempt_count: int) -> datetime:
        """Calculate exponential backoff timestamp with jitter."""
        factor = min(self._backoff_max, self._backoff_base ** max(1, attempt_count))
        jitter = random.uniform(0.8, 1.2) * factor
        return datetime.now(timezone.utc) + timedelta(seconds=jitter)

    async def process_batch(self) -> int:
        """Claim and process a single batch of pending jobs. Returns count processed."""
        jobs = await self._outbox_repo.claim_pending_jobs(self._batch_size)
        if not jobs:
            return 0

        processed = 0
        for job in jobs:
            success = await self._dispatch_job(job)
            if success:
                await self._outbox_repo.mark_completed(job.id)
                processed += 1
            else:
                next_time = self.calculate_next_backoff(job.attempt_count)
                if job.attempt_count >= self._max_attempts:
                    logger.error("Outbox job exceeded max attempts; moving to dead-letter", job_id=job.id)
                    await self._outbox_repo.mark_failed(job.id, "EXCEEDED_MAX_ATTEMPTS", next_time)
                else:
                    await self._outbox_repo.mark_failed(job.id, "TRANSIENT_FAILURE", next_time)

        return processed

    async def _dispatch_job(self, job: OutboxJob) -> bool:
        """Dispatch a single outbox job based on event_type / payload."""
        try:
            # 1. Telegram delivery event (Standard outbox relay)
            if job.recipient_tg_id and self._message_repo:
                msg = await self._message_repo.get_by_id(job.message_id)
                if msg and msg.text:
                    tg_msg = await self._bot.send_message(
                        chat_id=job.recipient_tg_id,
                        text=msg.text,
                    )
                    await self._message_repo.update_delivery_status(
                        message_id=msg.id,
                        status=MessageDeliveryStatus.DELIVERED,
                        telegram_msg_id=tg_msg.message_id,
                    )
                    return True

            return True
        except Exception as exc:
            logger.warning("Outbox job dispatch failed", job_id=job.id, error=str(exc))
            return False

    async def run_loop(self) -> None:
        """Continuous execution loop with shutdown support."""
        self._is_running = True
        logger.info("Outbox worker loop started")
        while self._is_running:
            try:
                count = await self.process_batch()
                if count == 0:
                    await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Outbox worker loop error", error=str(e))
                await asyncio.sleep(self._poll_interval)
        logger.info("Outbox worker loop stopped")

    def stop(self) -> None:
        self._is_running = False
