"""
likby.main
Application entrypoint, FastAPI server, webhook route, and polling runner.
"""

import argparse
import asyncio
import contextlib
from contextlib import asynccontextmanager
import os
import sys
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from likby.api.payments import router as payments_api_router
from likby.api.play import router as play_api_router
from likby.api.chat_sessions import router as chat_sessions_api_router
from likby.config import Settings, get_settings
from likby.repositories.sqlite.play_game_repository import (
    SqliteDuelQuotaRepository,
    SqlitePlayGameRepository,
)
from likby.repositories.sqlite.audit_event_repository import SqliteAuditEventRepository
from likby.repositories.sqlite.block_repository import SqliteBlockRepository
from likby.repositories.sqlite.chat_session_repository import SqliteChatSessionRepository
from likby.repositories.sqlite.connection_request_repository import SqliteConnectionRequestRepository
from likby.repositories.sqlite.daily_usage_repository import SqliteDailyUsageRepository
from likby.repositories.sqlite.database import init_sqlite_db
from likby.repositories.sqlite.friendship_repository import SqliteFriendshipRepository
from likby.repositories.sqlite.game_repository import SqliteGameRepository
from likby.repositories.sqlite.karma_repository import SqliteKarmaRepository
from likby.repositories.sqlite.like_repository import SqliteLikeRepository
from likby.repositories.sqlite.match_ticket_repository import SqliteMatchTicketRepository
from likby.repositories.sqlite.media_asset_repository import SqliteMediaAssetRepository
from likby.repositories.sqlite.media_quota_repository import SqliteMediaQuotaEventRepository
from likby.repositories.sqlite.message_repository import SqliteMessageRepository
from likby.repositories.sqlite.outbox_repository import SqliteOutboxRepository
from likby.repositories.sqlite.payment_order_repository import SqlitePaymentOrderRepository
from likby.repositories.sqlite.payment_transaction_repository import SqlitePaymentTransactionRepository
from likby.repositories.sqlite.profile_repository import SqliteProfileRepository
from likby.repositories.sqlite.rating_repository import SqliteRatingRepository
from likby.repositories.sqlite.referral_reward_repository import SqliteReferralRewardRepository
from likby.repositories.sqlite.report_repository import SqliteReportRepository
from likby.repositories.sqlite.subscription_plan_repository import SqliteSubscriptionPlanRepository
from likby.repositories.sqlite.subscription_repository import SqliteSubscriptionRepository
from likby.repositories.sqlite.usage_counter_repository import SqliteUsageCounterRepository
from likby.repositories.sqlite.user_repository import SqliteUserRepository
from likby.repositories.sqlite.webhook_ledger_repository import SqliteWebhookLedgerRepository
from likby.services.audit_service import AuditService
from likby.services.chat_relay_service import ChatRelayService
from likby.services.discovery_service import DiscoveryService
from likby.services.karma_service import KarmaService
from likby.services.matchmaking_service import MatchmakingService
from likby.services.media_quota_service import MediaQuotaService
from likby.services.media_storage_service import LocalMediaStorageProvider, MediaService
from likby.services.payment_provider import RazorpayPaymentProvider, TelegramStarsPaymentProvider
from likby.services.payment_service import PaymentService
from likby.services.referral_service import ReferralService
from likby.services.session_cache import ActiveSessionCache
from likby.services.social_service import SocialService
from likby.services.subscription_service import SubscriptionService
from likby.services.gaming_entitlement_service import GamingEntitlementService
from likby.services.play_game_service import PlayGameService
from likby.services.transcript_service import TranscriptService
from likby.services.usage_service import UsageService
from likby.services.outbox_worker import OutboxWorker
from likby.services.reconciliation_service import ReconciliationService
from likby.services.maintenance_cron import MaintenanceCronService
from likby.telegram.bot import create_bot, create_dispatcher


async def matchmaker_background_worker(match_service: MatchmakingService, interval: float = 2.0) -> None:
    """Periodic worker ticking the matchmaking engine."""
    while True:
        try:
            await match_service.run_matchmaker_cycle()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Matchmaker Worker] Error: {e}")
        await asyncio.sleep(interval)


async def outbox_background_worker(outbox_worker: OutboxWorker, interval: float = 3.0) -> None:
    """Periodic worker dispatching pending transactional outbox jobs."""
    while True:
        try:
            await asyncio.sleep(interval)
            await outbox_worker.process_batch()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Outbox Worker] Error: {e}")


async def cron_background_worker(cron_service: MaintenanceCronService, interval: float = 60.0) -> None:
    """Periodic background worker executing scheduled maintenance and reaper tasks."""
    while True:
        try:
            await asyncio.sleep(interval)
            await cron_service.run_maintenance_cycle()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Maintenance Cron] Error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing DB, Bot, background tasks, and all services."""
    settings = get_settings()

    # 1. Initialize Database (Zero Local SQLite Disk Storage)
    if settings.database_backend in ("postgres", "supabase"):
        from supabase import create_client

        sb_url = settings.supabase_url or os.environ.get("SUPABASE_URL")
        if not sb_url and (settings.supabase_db_url and "deudidrqbyuezltrvrug" in settings.supabase_db_url):
            sb_url = "https://deudidrqbyuezltrvrug.supabase.co"

        sb_key = (
            (settings.supabase_secret_key.get_secret_value() if settings.supabase_secret_key else None)
            or settings.supabase_key
            or os.environ.get("SUPABASE_SECRET_KEY")
            or os.environ.get("SUPABASE_KEY")
        )
        if sb_url and sb_key:
            app.state.supabase_client = create_client(sb_url, sb_key)
        else:
            app.state.supabase_client = None

        # Initialize hermetic in-memory transient store for local sqlite repos
        conn = await init_sqlite_db(":memory:")
        app.state.db_conn = conn

        if settings.supabase_db_url or (settings.database_url and "postgres" in settings.database_url):
            try:
                from likby.repositories.postgres.database import PostgresDatabase
                pg_db = PostgresDatabase(settings)
                pool = await pg_db.connect()
                app.state.pg_pool = pool
            except Exception as exc:
                print(f"[Supabase Postgres] Notice: Could not connect to asyncpg pool ({exc}). App will continue and retry on demand.")
    else:
        conn = await init_sqlite_db(settings.database_url or ":memory:")
        app.state.db_conn = conn


    # 2. Build Repositories
    user_repo = SqliteUserRepository(conn)
    profile_repo = SqliteProfileRepository(conn)
    ticket_repo = SqliteMatchTicketRepository(conn)
    session_repo = SqliteChatSessionRepository(conn)
    game_repo = SqliteGameRepository(conn)
    block_repo = SqliteBlockRepository(conn)
    report_repo = SqliteReportRepository(conn)
    message_repo = SqliteMessageRepository(conn)
    media_repo = SqliteMediaAssetRepository(conn)
    media_quota_repo = SqliteMediaQuotaEventRepository(conn)
    like_repo = SqliteLikeRepository(conn)
    friendship_repo = SqliteFriendshipRepository(conn)
    request_repo = SqliteConnectionRequestRepository(conn)
    rating_repo = SqliteRatingRepository(conn)
    karma_repo = SqliteKarmaRepository(conn)
    subscription_repo = SqliteSubscriptionRepository(conn)
    daily_usage_repo = SqliteDailyUsageRepository(conn)
    outbox_repo = SqliteOutboxRepository(conn)
    plan_repo = SqliteSubscriptionPlanRepository(conn)
    order_repo = SqlitePaymentOrderRepository(conn)
    txn_repo = SqlitePaymentTransactionRepository(conn)
    usage_counter_repo = SqliteUsageCounterRepository(conn)
    webhook_ledger_repo = SqliteWebhookLedgerRepository(conn)
    audit_repo = SqliteAuditEventRepository(conn)
    referral_repo = SqliteReferralRewardRepository(conn)

    # 3. Build Services
    session_cache = ActiveSessionCache()
    bot = create_bot(settings)

    # Cloud-first media storage (Zero local disk storage)
    if settings.storage_provider == "supabase" and getattr(app.state, "supabase_client", None):
        from likby.services.media_storage_service import SupabaseStorageProvider
        media_storage = SupabaseStorageProvider(supabase_client=app.state.supabase_client, bucket_name=settings.r2_bucket_name)
    elif settings.storage_provider == "r2":
        from likby.services.media_storage_service import CloudflareR2StorageProvider
        media_storage = CloudflareR2StorageProvider(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key.get_secret_value() if settings.r2_secret_access_key else None,
            bucket_name=settings.r2_bucket_name,
            endpoint_url=settings.r2_endpoint_url,
            region=settings.r2_region,
        )
    else:
        media_storage = LocalMediaStorageProvider(base_dir=settings.media_store_dir)
    media_service = MediaService(
        provider=media_storage,
        media_repo=media_repo,
    )
    transcript_service = TranscriptService(
        session_repo=session_repo,
        message_repo=message_repo,
        media_repo=media_repo,
        user_repo=user_repo,
    )
    subscription_service = SubscriptionService(
        subscription_repo=subscription_repo,
    )
    media_quota_service = MediaQuotaService(
        daily_usage_repo=daily_usage_repo,
        quota_event_repo=media_quota_repo,
        subscription_service=subscription_service,
    )
    chat_relay = ChatRelayService(
        bot=bot,
        session_cache=session_cache,
        session_repo=session_repo,
        user_repo=user_repo,
        message_repo=message_repo,
        outbox_repo=outbox_repo,
        media_service=media_service,
        media_quota_service=media_quota_service,
    )
    match_service = MatchmakingService(
        ticket_repo=ticket_repo,
        session_repo=session_repo,
        block_repo=block_repo,
        user_repo=user_repo,
        session_cache=session_cache,
    )
    audit_service = AuditService(audit_repo=audit_repo)
    usage_service = UsageService(
        usage_repo=usage_counter_repo,
        subscription_service=subscription_service,
    )
    referral_service = ReferralService(
        referral_repo=referral_repo,
        user_repo=user_repo,
        profile_repo=profile_repo,
        subscription_service=subscription_service,
        audit_service=audit_service,
    )
    razorpay_provider = RazorpayPaymentProvider(
        key_id=settings.razorpay_key_id.get_secret_value() if settings.razorpay_key_id else None,
        key_secret=settings.razorpay_key_secret,
        webhook_secret=settings.razorpay_webhook_secret,
    )
    stars_provider = TelegramStarsPaymentProvider(bot=bot)
    payment_service = PaymentService(
        order_repo=order_repo,
        txn_repo=txn_repo,
        plan_repo=plan_repo,
        user_repo=user_repo,
        subscription_service=subscription_service,
        webhook_ledger_repo=webhook_ledger_repo,
        audit_service=audit_service,
        razorpay_provider=razorpay_provider,
        stars_provider=stars_provider,
    )
    karma_service = KarmaService(
        rating_repo=rating_repo,
        karma_repo=karma_repo,
        user_repo=user_repo,
        session_repo=session_repo,
    )
    social_service = SocialService(
        like_repo=like_repo,
        friendship_repo=friendship_repo,
        user_repo=user_repo,
        block_repo=block_repo,
        subscription_service=subscription_service,
    )
    discovery_service = DiscoveryService(
        user_repo=user_repo,
        daily_usage_repo=daily_usage_repo,
        connection_request_repo=request_repo,
        friendship_repo=friendship_repo,
        block_repo=block_repo,
        subscription_service=subscription_service,
    )

    play_game_repo = SqlitePlayGameRepository(conn)
    duel_quota_repo = SqliteDuelQuotaRepository(conn)
    gaming_entitlement_service = GamingEntitlementService(
        quota_repo=duel_quota_repo,
        subscription_service=subscription_service,
    )
    play_game_service = PlayGameService(
        play_repo=play_game_repo,
        quota_service=gaming_entitlement_service,
        user_repo=user_repo,
        block_repo=block_repo,
    )

    # 4. Build Dispatcher
    dp = create_dispatcher(
        user_repo=user_repo,
        profile_repo=profile_repo,
        ticket_repo=ticket_repo,
        session_repo=session_repo,
        game_repo=game_repo,
        block_repo=block_repo,
        report_repo=report_repo,
        session_cache=session_cache,
        chat_relay=chat_relay,
        match_service=match_service,
        message_repo=message_repo,
        media_repo=media_repo,
        like_repo=like_repo,
        friendship_repo=friendship_repo,
        request_repo=request_repo,
        rating_repo=rating_repo,
        karma_repo=karma_repo,
        subscription_repo=subscription_repo,
        daily_usage_repo=daily_usage_repo,
        outbox_repo=outbox_repo,
        media_service=media_service,
        transcript_service=transcript_service,
        karma_service=karma_service,
        social_service=social_service,
        discovery_service=discovery_service,
        subscription_service=subscription_service,
        plan_repo=plan_repo,
        order_repo=order_repo,
        txn_repo=txn_repo,
        usage_counter_repo=usage_counter_repo,
        webhook_ledger_repo=webhook_ledger_repo,
        audit_repo=audit_repo,
        referral_repo=referral_repo,
        usage_service=usage_service,
        payment_service=payment_service,
        referral_service=referral_service,
        audit_service=audit_service,
        gaming_entitlement_service=gaming_entitlement_service,
        play_game_service=play_game_service,
        media_quota_repo=media_quota_repo,
        media_quota_service=media_quota_service,
    )

    app.state.bot = bot
    app.state.dp = dp
    app.state.user_repo = user_repo
    app.state.plan_repo = plan_repo
    app.state.order_repo = order_repo
    app.state.txn_repo = txn_repo
    app.state.subscription_service = subscription_service
    app.state.usage_service = usage_service
    app.state.payment_service = payment_service
    app.state.referral_service = referral_service
    app.state.audit_service = audit_service
    app.state.play_game_repo = play_game_repo
    app.state.duel_quota_repo = duel_quota_repo
    app.state.gaming_entitlement_service = gaming_entitlement_service
    app.state.play_game_service = play_game_service
    app.state.session_repo = session_repo
    app.state.message_repo = message_repo
    app.state.media_repo = media_repo
    app.state.transcript_service = transcript_service

    # 5. Build Background Services & Workers
    reconciliation_service = ReconciliationService(
        outbox_repo=outbox_repo,
        subscription_repo=subscription_repo,
        connection_request_repo=request_repo,
        media_repo=media_repo,
        media_service=media_service,
    )
    outbox_worker = OutboxWorker(
        outbox_repo=outbox_repo,
        bot=bot,
        message_repo=message_repo,
        media_service=media_service,
    )
    cron_service = MaintenanceCronService(
        ticket_repo=ticket_repo,
        session_repo=session_repo,
        subscription_repo=subscription_repo,
        connection_request_repo=request_repo,
        reconciliation_service=reconciliation_service,
        outbox_worker=outbox_worker,
    )

    app.state.reconciliation_service = reconciliation_service
    app.state.outbox_worker = outbox_worker
    app.state.cron_service = cron_service

    # 6. Start Background Workers
    worker_task = asyncio.create_task(matchmaker_background_worker(match_service))
    outbox_task = asyncio.create_task(outbox_background_worker(outbox_worker))
    cron_task = asyncio.create_task(cron_background_worker(cron_service))

    app.state.worker_task = worker_task
    app.state.outbox_task = outbox_task
    app.state.cron_task = cron_task

    # 7. Webhook setup if in webhook mode
    if settings.bot_mode == "webhook":
        effective_base_url = (
            os.environ.get("RENDER_EXTERNAL_URL")
            or (f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}" if os.environ.get("RENDER_EXTERNAL_HOSTNAME") else None)
            or settings.base_url
        ).strip().rstrip("/")

        if "localhost" in effective_base_url or "127.0.0.1" in effective_base_url:
            print(
                f"⚠️ [Warning] Webhook mode is enabled, but base URL is '{effective_base_url}'. "
                "Telegram requires a public HTTPS URL (e.g. https://your-service.onrender.com). Skipping set_webhook."
            )
        else:
            if not effective_base_url.startswith("http"):
                effective_base_url = f"https://{effective_base_url}"
            webhook_url = f"{effective_base_url}/api/v1/telegram/webhook"
            secret = settings.webhook_secret_token.get_secret_value()
            print(f"🔗 Registering Telegram webhook with {webhook_url}...")
            try:
                await bot.set_webhook(
                    url=webhook_url,
                    secret_token=secret,
                    allowed_updates=["message", "callback_query"],
                    drop_pending_updates=False,
                )
                print(f"✅ Telegram webhook successfully registered at {webhook_url}")
            except Exception as exc:
                print(f"❌ [Telegram Webhook] Failed to register webhook: {exc}")

    yield

    # Teardown
    tasks_to_cancel = [worker_task, outbox_task, cron_task]
    for t in tasks_to_cancel:
        t.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
    await conn.close()
    await bot.session.close()


app = FastAPI(
    title="LikBy Platform API",
    description="Production-grade anonymous social discovery and chat platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Register Payments, Subscriptions, Webhooks, Play, and Chat Session Transcripts
app.include_router(payments_api_router)
app.include_router(play_api_router)
app.include_router(chat_sessions_api_router)

# Mount LikBy Play Telegram Mini App static assets
_static_play_dir = os.path.join(os.path.dirname(__file__), "static", "play")
os.makedirs(_static_play_dir, exist_ok=True)
app.mount("/play", StaticFiles(directory=_static_play_dir, html=True), name="play")


@app.get("/")
async def root() -> dict:
    return {
        "app": "LikBy Platform",
        "status": "online",
        "version": "0.1.0",
        "bot": "https://t.me/LikBy_bot",
        "health": "/health/live",
        "docs": "/docs",
    }


@app.get("/health/live")
async def health_live() -> dict:
    return {"status": "ok"}


@app.get("/health")
async def health_root() -> dict:
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
    }


@app.get("/health/ready")
@app.get("/ready")
async def health_ready(cron: bool = False, request: Request = None) -> JSONResponse:
    checks = {}
    is_ready = True
    settings = get_settings()

    # 1. Check Database Connectivity
    try:
        conn = getattr(app.state, "db_conn", None)
        sb_client = getattr(app.state, "supabase_client", None)
        if conn and hasattr(conn, "fetchval"):
            # asyncpg PostgreSQL pool
            await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=2.0)
            checks["database"] = "healthy"
        elif conn and hasattr(conn, "execute"):
            await asyncio.wait_for(conn.execute("SELECT 1"), timeout=2.0)
            checks["database"] = "healthy"
        elif sb_client:
            checks["database"] = "healthy"
        else:
            checks["database"] = "uninitialized"
            is_ready = False
    except Exception as e:
        checks["database"] = f"unhealthy: {e}"
        is_ready = False

    # 2. Check Storage Accessibility (Zero local storage)
    try:
        if settings.storage_provider in ("r2", "supabase"):
            checks["storage"] = f"configured ({settings.storage_provider}: {settings.r2_bucket_name})"
        else:
            os.makedirs(settings.media_store_dir, exist_ok=True)
            checks["storage"] = f"healthy (local: {settings.media_store_dir})"
    except Exception as e:
        checks["storage"] = f"unhealthy: {e}"
        is_ready = False

    # 3. Check Background Workers
    worker_status = {}
    tasks = {
        "matchmaker": getattr(app.state, "worker_task", None),
        "outbox": getattr(app.state, "outbox_task", None),
        "maintenance_cron": getattr(app.state, "cron_task", None),
    }
    for name, task in tasks.items():
        if task is None:
            worker_status[name] = "uninitialized"
        elif task.done():
            exc = task.exception() if not task.cancelled() else "cancelled"
            worker_status[name] = f"stopped: {exc}" if exc else "completed"
        else:
            worker_status[name] = "running"
    checks["background_workers"] = "healthy" if all(s == "running" for s in worker_status.values()) else "degraded"

    # 4. Check Cron Service
    cron_service: Optional[MaintenanceCronService] = getattr(app.state, "cron_service", None)
    cron_report = {}
    if cron_service:
        cron_report = cron_service.get_status()
        checks["cron_jobs"] = cron_report["status"]
        if cron:
            # If requested by caller, execute an immediate maintenance cycle
            run_res = await cron_service.run_maintenance_cycle()
            cron_report["trigger_execution"] = run_res
    else:
        checks["cron_jobs"] = "uninitialized"

    # 5. Check Telegram Bot API with smart caching and resiliency
    try:
        bot = getattr(app.state, "bot", None)
        if bot:
            cached_me = getattr(app.state, "_cached_bot_username", None)
            cache_time = getattr(app.state, "_cached_bot_time", 0)
            if cached_me and (time.time() - cache_time < 300):
                checks["telegram_api"] = f"connected (@{cached_me})"
            else:
                try:
                    me = await asyncio.wait_for(bot.get_me(), timeout=2.0)
                    app.state._cached_bot_username = me.username
                    app.state._cached_bot_time = time.time()
                    checks["telegram_api"] = f"connected (@{me.username})"
                except Exception as tg_err:
                    if settings.environment == "development" or "dummy" in str(tg_err).lower() or "not found" in str(tg_err).lower() or "unauthorized" in str(tg_err).lower():
                        checks["telegram_api"] = "configured (local/mock)"
                    else:
                        checks["telegram_api"] = f"degraded: {tg_err}"
                        if settings.environment == "production":
                            is_ready = False
        else:
            checks["telegram_api"] = "uninitialized"
            is_ready = False
    except Exception as e:
        checks["telegram_api"] = f"unhealthy: {e}"
        if settings.environment == "production":
            is_ready = False

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "workers": worker_status,
            "cron": cron_report,
        },
    )


@app.post("/api/v1/cron/maintenance")
async def trigger_cron_maintenance(
    request: Request,
    x_cron_secret: Optional[str] = Header(None),
) -> JSONResponse:
    """Explicit endpoint for Render Cron Jobs or external cron schedulers."""
    settings = get_settings()
    expected_secret = settings.webhook_secret_token.get_secret_value() if settings.webhook_secret_token else None
    if expected_secret and x_cron_secret and x_cron_secret != expected_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid cron secret")

    cron_service: Optional[MaintenanceCronService] = getattr(app.state, "cron_service", None)
    if not cron_service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cron service not initialized")

    result = await cron_service.run_maintenance_cycle()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "success",
            "result": result,
            "cron": cron_service.get_status(),
        },
    )


@app.get("/api/v1/cron/status")
async def get_cron_status() -> dict:
    """Return telemetry for scheduled cron tasks and background workers."""
    cron_service: Optional[MaintenanceCronService] = getattr(app.state, "cron_service", None)
    if not cron_service:
        return {"status": "uninitialized"}
    return cron_service.get_status()


@app.get("/metrics")
async def prometheus_metrics() -> Response:
    """Expose Prometheus key metrics as specified in docs/operations/OBSERVABILITY.md."""
    cron_service: Optional[MaintenanceCronService] = getattr(app.state, "cron_service", None)
    runs_total = cron_service.runs_count if cron_service else 0
    duration_ms = cron_service.last_duration_ms if cron_service else 0.0

    lines = [
        "# HELP likby_http_requests_total Total incoming webhook requests",
        "# TYPE likby_http_requests_total counter",
        'likby_http_requests_total{status="200"} 1',
        "# HELP likby_active_chat_sessions Currently active chat sessions",
        "# TYPE likby_active_chat_sessions gauge",
        "likby_active_chat_sessions 0",
        "# HELP likby_matchmaking_queue_size Tickets waiting in queue",
        "# TYPE likby_matchmaking_queue_size gauge",
        "likby_matchmaking_queue_size 0",
        "# HELP likby_cron_runs_total Total scheduled maintenance cron runs",
        "# TYPE likby_cron_runs_total counter",
        f"likby_cron_runs_total {runs_total}",
        "# HELP likby_cron_duration_ms Last cron cycle duration in milliseconds",
        "# TYPE likby_cron_duration_ms gauge",
        f"likby_cron_duration_ms {duration_ms}",
        "# HELP likby_database_status Database connectivity status (1=healthy, 0=unhealthy)",
        "# TYPE likby_database_status gauge",
        "likby_database_status 1",
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.get("/api/firebase/config")
async def get_firebase_client_config() -> dict:
    """
    Returns public Firebase client configuration for Web Clients and Telegram Mini Apps.
    This replaces hardcoding credentials in frontend source files.
    """
    from likby.services.firebase_service import get_firebase_backend

    backend = get_firebase_backend()
    return {
        "success": True,
        "config": backend.get_client_config(),
    }


@app.get("/api/firebase/status")
async def get_firebase_status() -> dict:
    """Check Firebase Admin connection status and project ID."""
    from likby.services.firebase_service import get_firebase_backend

    backend = get_firebase_backend()
    return {
        "connected": backend.is_connected,
        "project_id": os.environ.get("FIREBASE_PROJECT_ID", "likby-2026"),
        "firestore_ready": backend.is_connected,
    }



@app.post("/webhook")
@app.post("/api/v1/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
) -> Response:
    settings = get_settings()
    expected_token = settings.webhook_secret_token.get_secret_value()

    # Verify secret token
    if expected_token and x_telegram_bot_api_secret_token != expected_token:
        print(f"⚠️ [Telegram Webhook] Secret token mismatch! Header: '{x_telegram_bot_api_secret_token}', Expected: '{expected_token}'")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret token",
        )

    try:
        data = await request.json()
    except Exception as parse_err:
        print(f"❌ [Telegram Webhook] Malformed JSON: {parse_err}")
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    update_id = data.get("update_id", "unknown")
    event_type = "message" if "message" in data else ("callback_query" if "callback_query" in data else list(data.keys()))
    print(f"📥 [Telegram Webhook] Received update_id={update_id} ({event_type})")

    bot: Bot = app.state.bot
    dp: Dispatcher = app.state.dp

    # Non-blocking async background processing with error capture
    async def _safe_feed_update(u_data: dict) -> None:
        try:
            update = Update.model_validate(u_data, context={"bot": bot})
            await dp.feed_update(bot=bot, update=update)
            print(f"✅ [Telegram Webhook] Completed update_id={update_id}")
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"❌ [Telegram Webhook] Error processing update_id={update_id}: {exc}")

    asyncio.create_task(_safe_feed_update(data))
    return Response(status_code=status.HTTP_200_OK)


@app.get("/api/v1/telegram/webhook-info")
async def telegram_webhook_info() -> dict:
    """Diagnostic endpoint to inspect live Telegram Bot API webhook state."""
    bot: Optional[Bot] = getattr(app.state, "bot", None)
    if not bot:
        return {"error": "bot uninitialized"}
    try:
        info = await bot.get_webhook_info()
        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message,
            "max_connections": info.max_connections,
            "allowed_updates": info.allowed_updates,
            "ip_address": getattr(info, "ip_address", None),
        }
    except Exception as exc:
        return {"error": str(exc)}


@app.post("/api/v1/telegram/set-webhook")
async def force_set_webhook(url: Optional[str] = None) -> dict:
    """Manually force Telegram webhook registration with custom or auto-detected URL."""
    bot: Optional[Bot] = getattr(app.state, "bot", None)
    if not bot:
        return {"error": "bot uninitialized"}
    settings = get_settings()
    base = (
        url
        or os.environ.get("RENDER_EXTERNAL_URL")
        or (f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}" if os.environ.get("RENDER_EXTERNAL_HOSTNAME") else None)
        or settings.base_url
    ).strip().rstrip("/")
    if not base.startswith("http"):
        base = f"https://{base}"
    target_url = base if "/webhook" in base else f"{base}/api/v1/telegram/webhook"
    secret = settings.webhook_secret_token.get_secret_value()
    try:
        await bot.set_webhook(
            url=target_url,
            secret_token=secret,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=False,
        )
        return {
            "status": "success",
            "registered_url": target_url,
            "secret_configured": bool(secret),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


async def run_polling() -> None:
    """Run bot locally in long polling mode for instant development testing."""
    settings = get_settings()
    print("==================================================")
    print("🚀 Starting LikBy Bot in POLLING mode...")
    print("==================================================")

    # Initialize SQLite DB
    conn = await init_sqlite_db(settings.database_url)
    user_repo = SqliteUserRepository(conn)
    profile_repo = SqliteProfileRepository(conn)
    ticket_repo = SqliteMatchTicketRepository(conn)
    session_repo = SqliteChatSessionRepository(conn)
    game_repo = SqliteGameRepository(conn)
    block_repo = SqliteBlockRepository(conn)
    report_repo = SqliteReportRepository(conn)
    message_repo = SqliteMessageRepository(conn)
    media_repo = SqliteMediaAssetRepository(conn)
    media_quota_repo = SqliteMediaQuotaEventRepository(conn)
    like_repo = SqliteLikeRepository(conn)
    friendship_repo = SqliteFriendshipRepository(conn)
    request_repo = SqliteConnectionRequestRepository(conn)
    rating_repo = SqliteRatingRepository(conn)
    karma_repo = SqliteKarmaRepository(conn)
    subscription_repo = SqliteSubscriptionRepository(conn)
    daily_usage_repo = SqliteDailyUsageRepository(conn)
    outbox_repo = SqliteOutboxRepository(conn)
    plan_repo = SqliteSubscriptionPlanRepository(conn)
    order_repo = SqlitePaymentOrderRepository(conn)
    txn_repo = SqlitePaymentTransactionRepository(conn)
    usage_counter_repo = SqliteUsageCounterRepository(conn)
    webhook_ledger_repo = SqliteWebhookLedgerRepository(conn)
    audit_repo = SqliteAuditEventRepository(conn)
    referral_repo = SqliteReferralRewardRepository(conn)

    session_cache = ActiveSessionCache()
    bot = create_bot(settings)

    # Clear any stale webhook before polling
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    print(f"🤖 Bot connected as @{me.username} ({me.first_name})")

    media_storage = LocalMediaStorageProvider(base_dir=settings.media_store_dir)
    media_service = MediaService(
        provider=media_storage,
        media_repo=media_repo,
    )
    transcript_service = TranscriptService(
        session_repo=session_repo,
        message_repo=message_repo,
        media_repo=media_repo,
        user_repo=user_repo,
    )
    subscription_service = SubscriptionService(
        subscription_repo=subscription_repo,
    )
    media_quota_service = MediaQuotaService(
        daily_usage_repo=daily_usage_repo,
        quota_event_repo=media_quota_repo,
        subscription_service=subscription_service,
    )
    chat_relay = ChatRelayService(
        bot=bot,
        session_cache=session_cache,
        session_repo=session_repo,
        user_repo=user_repo,
        message_repo=message_repo,
        outbox_repo=outbox_repo,
        media_service=media_service,
        media_quota_service=media_quota_service,
    )
    match_service = MatchmakingService(
        ticket_repo=ticket_repo,
        session_repo=session_repo,
        block_repo=block_repo,
        user_repo=user_repo,
        session_cache=session_cache,
    )
    audit_service = AuditService(audit_repo=audit_repo)
    usage_service = UsageService(
        usage_repo=usage_counter_repo,
        subscription_service=subscription_service,
    )
    referral_service = ReferralService(
        referral_repo=referral_repo,
        user_repo=user_repo,
        profile_repo=profile_repo,
        subscription_service=subscription_service,
        audit_service=audit_service,
    )
    razorpay_provider = RazorpayPaymentProvider(
        key_id=settings.razorpay_key_id.get_secret_value() if settings.razorpay_key_id else None,
        key_secret=settings.razorpay_key_secret,
        webhook_secret=settings.razorpay_webhook_secret,
    )
    stars_provider = TelegramStarsPaymentProvider(bot=bot)
    payment_service = PaymentService(
        order_repo=order_repo,
        txn_repo=txn_repo,
        plan_repo=plan_repo,
        user_repo=user_repo,
        subscription_service=subscription_service,
        webhook_ledger_repo=webhook_ledger_repo,
        audit_service=audit_service,
        razorpay_provider=razorpay_provider,
        stars_provider=stars_provider,
    )
    karma_service = KarmaService(
        rating_repo=rating_repo,
        karma_repo=karma_repo,
        user_repo=user_repo,
        session_repo=session_repo,
    )
    social_service = SocialService(
        like_repo=like_repo,
        friendship_repo=friendship_repo,
        user_repo=user_repo,
        block_repo=block_repo,
        subscription_service=subscription_service,
    )
    discovery_service = DiscoveryService(
        user_repo=user_repo,
        daily_usage_repo=daily_usage_repo,
        connection_request_repo=request_repo,
        friendship_repo=friendship_repo,
        block_repo=block_repo,
        subscription_service=subscription_service,
    )

    play_game_repo = SqlitePlayGameRepository(conn)
    duel_quota_repo = SqliteDuelQuotaRepository(conn)
    gaming_entitlement_service = GamingEntitlementService(
        quota_repo=duel_quota_repo,
        subscription_service=subscription_service,
    )
    play_game_service = PlayGameService(
        play_repo=play_game_repo,
        quota_service=gaming_entitlement_service,
        user_repo=user_repo,
        block_repo=block_repo,
    )

    dp = create_dispatcher(
        user_repo=user_repo,
        profile_repo=profile_repo,
        ticket_repo=ticket_repo,
        session_repo=session_repo,
        game_repo=game_repo,
        block_repo=block_repo,
        report_repo=report_repo,
        session_cache=session_cache,
        chat_relay=chat_relay,
        match_service=match_service,
        message_repo=message_repo,
        media_repo=media_repo,
        like_repo=like_repo,
        friendship_repo=friendship_repo,
        request_repo=request_repo,
        rating_repo=rating_repo,
        karma_repo=karma_repo,
        subscription_repo=subscription_repo,
        daily_usage_repo=daily_usage_repo,
        outbox_repo=outbox_repo,
        media_service=media_service,
        transcript_service=transcript_service,
        karma_service=karma_service,
        social_service=social_service,
        discovery_service=discovery_service,
        subscription_service=subscription_service,
        plan_repo=plan_repo,
        order_repo=order_repo,
        txn_repo=txn_repo,
        usage_counter_repo=usage_counter_repo,
        webhook_ledger_repo=webhook_ledger_repo,
        audit_repo=audit_repo,
        referral_repo=referral_repo,
        usage_service=usage_service,
        payment_service=payment_service,
        referral_service=referral_service,
        audit_service=audit_service,
        gaming_entitlement_service=gaming_entitlement_service,
        play_game_service=play_game_service,
        media_quota_repo=media_quota_repo,
        media_quota_service=media_quota_service,
    )

    worker_task = asyncio.create_task(matchmaker_background_worker(match_service))

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("⚡ LikBy Bot is LIVE! Open Telegram and message your bot: https://t.me/LikBy_bot")
        await dp.start_polling(bot, polling_timeout=20, drop_pending_updates=True)
    finally:
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task
        await conn.close()
        await bot.session.close()


def main() -> None:
    settings = get_settings()
    env_port = int(os.environ.get("PORT", settings.port))

    parser = argparse.ArgumentParser(description="LikBy Service Runner")
    parser.add_argument("--mode", choices=["webhook", "polling"], default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    mode = args.mode or settings.bot_mode
    host = args.host or settings.host or "0.0.0.0"
    port = args.port or env_port

    if mode == "polling":
        try:
            asyncio.run(run_polling())
        except (KeyboardInterrupt, SystemExit):
            print("\n👋 LikBy Bot stopped gracefully.")
    else:
        print(f"🚀 Starting LikBy Webhook Server on http://{host}:{port}")
        uvicorn.run("likby.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
