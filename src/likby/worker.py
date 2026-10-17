"""
likby.worker
Standalone background worker process for Render.
Processes durable outbox jobs, media archival, and cross-service reconciliation.
"""

import asyncio
import signal
import sys
import aiosqlite
import structlog
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from likby.config import get_settings
from likby.repositories.sqlite.database import init_db
from likby.repositories.sqlite.media_asset_repository import SqliteMediaAssetRepository
from likby.repositories.sqlite.message_repository import SqliteMessageRepository
from likby.repositories.sqlite.outbox_repository import SqliteOutboxRepository
from likby.services.media_storage_service import (
    CloudflareR2StorageProvider,
    LocalMediaStorageProvider,
    MediaService,
)
from likby.services.outbox_worker import OutboxWorker
from likby.services.reconciliation_service import ReconciliationService

logger = structlog.get_logger(__name__)


async def main() -> None:
    settings = get_settings()
    logger.info("Initializing LikBy background worker", env=settings.environment)

    # 1. Initialize Bot instance for deliveries
    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # 2. Database Connection
    if settings.database_backend == "postgres":
        from likby.repositories.postgres.database import PostgresDatabase
        from likby.repositories.postgres.media_asset_repository import PostgresMediaAssetRepository
        from likby.repositories.postgres.outbox_repository import PostgresOutboxRepository

        pg_db = PostgresDatabase(settings)
        pool = await pg_db.connect()
        outbox_repo = PostgresOutboxRepository(pool)
        media_repo = PostgresMediaAssetRepository(pool)
        message_repo = None  # Or Firestore repository
    else:
        # SQLite
        db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
        conn = await aiosqlite.connect(db_path)
        await init_db(conn)
        outbox_repo = SqliteOutboxRepository(conn)
        media_repo = SqliteMediaAssetRepository(conn)
        message_repo = SqliteMessageRepository(conn)

    # 3. Media Storage
    if settings.storage_provider == "r2":
        sec_key = settings.r2_secret_access_key.get_secret_value() if settings.r2_secret_access_key else ""
        provider = CloudflareR2StorageProvider(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=sec_key,
            bucket_name=settings.r2_bucket_name,
            endpoint_url=settings.r2_endpoint_url,
            region=settings.r2_region,
        )
    else:
        provider = LocalMediaStorageProvider(base_dir=settings.media_store_dir)

    media_service = MediaService(
        provider=provider,
        media_repo=media_repo,
        environment=settings.environment,
        bucket_name=settings.r2_bucket_name,
    )

    # 4. Outbox & Reconciliation Services
    worker = OutboxWorker(
        outbox_repo=outbox_repo,
        bot=bot,
        message_repo=message_repo,
        media_service=media_service,
        batch_size=settings.outbox_batch_size,
        poll_interval=settings.outbox_poll_interval_seconds,
        max_attempts=settings.outbox_max_attempts,
        backoff_base=settings.outbox_backoff_base_seconds,
        backoff_max=settings.outbox_backoff_max_seconds,
    )

    reconciler = ReconciliationService(
        outbox_repo=outbox_repo,
        media_repo=media_repo,
        media_service=media_service,
    )

    # Signal Handling
    stop_event = asyncio.Event()

    def handle_signal():
        logger.info("Termination signal received, stopping worker...")
        worker.stop()
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Windows signal handling fallback
            pass

    # Launch outbox processing and periodic reconciliation
    worker_task = asyncio.create_task(worker.run_loop())

    async def periodic_reconciliation():
        while not stop_event.is_set():
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                await reconciler.run_full_reconciliation()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Periodic reconciliation error", error=str(e))

    recon_task = asyncio.create_task(periodic_reconciliation())

    logger.info("Worker services active. Awaiting jobs...")
    await stop_event.wait()

    # Graceful shutdown
    worker.stop()
    recon_task.cancel()
    worker_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.gather(worker_task, recon_task)

    if settings.database_backend == "postgres":
        await pg_db.close()
    else:
        await conn.close()
    await bot.session.close()
    logger.info("Worker shutdown clean.")


if __name__ == "__main__":
    import contextlib
    asyncio.run(main())
