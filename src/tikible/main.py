"""
tikible.main
Application entrypoint, FastAPI server, webhook route, and polling runner.
"""

import argparse
import asyncio
from contextlib import asynccontextmanager
import sys
from typing import AsyncGenerator
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
import uvicorn
from tikible.config import Settings, get_settings
from tikible.repositories.sqlite.block_repository import SqliteBlockRepository
from tikible.repositories.sqlite.chat_session_repository import SqliteChatSessionRepository
from tikible.repositories.sqlite.database import init_sqlite_db
from tikible.repositories.sqlite.game_repository import SqliteGameRepository
from tikible.repositories.sqlite.match_ticket_repository import SqliteMatchTicketRepository
from tikible.repositories.sqlite.profile_repository import SqliteProfileRepository
from tikible.repositories.sqlite.report_repository import SqliteReportRepository
from tikible.repositories.sqlite.user_repository import SqliteUserRepository
from tikible.services.chat_relay_service import ChatRelayService
from tikible.services.matchmaking_service import MatchmakingService
from tikible.services.session_cache import ActiveSessionCache
from tikible.telegram.bot import create_bot, create_dispatcher


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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing DB, Bot, and background tasks."""
    settings = get_settings()

    # 1. Initialize SQLite Database
    conn = await init_sqlite_db(settings.database_url)
    app.state.db_conn = conn

    # 2. Build Repositories
    user_repo = SqliteUserRepository(conn)
    profile_repo = SqliteProfileRepository(conn)
    ticket_repo = SqliteMatchTicketRepository(conn)
    session_repo = SqliteChatSessionRepository(conn)
    game_repo = SqliteGameRepository(conn)
    block_repo = SqliteBlockRepository(conn)
    report_repo = SqliteReportRepository(conn)

    # 3. Build Services
    session_cache = ActiveSessionCache()
    bot = create_bot(settings)
    chat_relay = ChatRelayService(
        bot=bot,
        session_cache=session_cache,
        session_repo=session_repo,
        user_repo=user_repo,
    )
    match_service = MatchmakingService(
        ticket_repo=ticket_repo,
        session_repo=session_repo,
        block_repo=block_repo,
        user_repo=user_repo,
        session_cache=session_cache,
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
    )

    app.state.bot = bot
    app.state.dp = dp

    # 5. Start Background Matchmaker Loop
    worker_task = asyncio.create_task(matchmaker_background_worker(match_service))
    app.state.worker_task = worker_task

    # 6. Webhook setup if in webhook mode
    if settings.bot_mode == "webhook":
        webhook_url = f"{settings.base_url}/api/v1/telegram/webhook"
        await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret_token.get_secret_value(),
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=False,
        )

    yield

    # Teardown
    worker_task.cancel()
    await conn.close()
    await bot.session.close()


app = FastAPI(
    title="LikBy Platform API",
    description="Privacy-first anonymous social matching platform",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health/live")
async def health_live() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> JSONResponse:
    checks = {}
    is_ready = True

    # Check Database
    try:
        conn = getattr(app.state, "db_conn", None)
        if conn:
            await conn.execute("SELECT 1")
            checks["database"] = "healthy"
        else:
            checks["database"] = "uninitialized"
            is_ready = False
    except Exception as e:
        checks["database"] = f"unhealthy: {e}"
        is_ready = False

    # Check Bot Token
    try:
        bot = getattr(app.state, "bot", None)
        if bot:
            me = await bot.get_me()
            checks["telegram_api"] = f"connected (@{me.username})"
        else:
            checks["telegram_api"] = "uninitialized"
            is_ready = False
    except Exception as e:
        checks["telegram_api"] = f"unhealthy: {e}"
        is_ready = False

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if is_ready else "degraded", "checks": checks},
    )


@app.post("/api/v1/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None),
) -> Response:
    settings = get_settings()
    expected_token = settings.webhook_secret_token.get_secret_value()

    # Verify secret token
    if x_telegram_bot_api_secret_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret token",
        )

    data = await request.json()
    bot: Bot = app.state.bot
    dp: Dispatcher = app.state.dp

    # Non-blocking async background processing
    update = Update.model_validate(data, context={"bot": bot})
    asyncio.create_task(dp.feed_update(bot=bot, update=update))

    return Response(status_code=status.HTTP_200_OK)


async def run_polling() -> None:
    """Run bot locally in long polling mode for instant development testing."""
    settings = get_settings()
    print("==================================================")
    print("🚀 Starting LikBy Bot in POLLING mode...")
    print("==================================================")

    # Clean local DB
    conn = await init_sqlite_db(settings.database_url)
    user_repo = SqliteUserRepository(conn)
    profile_repo = SqliteProfileRepository(conn)
    ticket_repo = SqliteMatchTicketRepository(conn)
    session_repo = SqliteChatSessionRepository(conn)
    game_repo = SqliteGameRepository(conn)
    block_repo = SqliteBlockRepository(conn)
    report_repo = SqliteReportRepository(conn)

    session_cache = ActiveSessionCache()
    bot = create_bot(settings)

    # Clear any stale webhook before polling
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    print(f"🤖 Bot connected as @{me.username} ({me.first_name})")

    chat_relay = ChatRelayService(
        bot=bot,
        session_cache=session_cache,
        session_repo=session_repo,
        user_repo=user_repo,
    )
    match_service = MatchmakingService(
        ticket_repo=ticket_repo,
        session_repo=session_repo,
        block_repo=block_repo,
        user_repo=user_repo,
        session_cache=session_cache,
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
    )

    worker_task = asyncio.create_task(matchmaker_background_worker(match_service))

    try:
        print("⚡ LikBy Bot is LIVE! Open Telegram and message your bot: https://t.me/LikBy_bot")
        await dp.start_polling(bot)
    finally:
        worker_task.cancel()
        await conn.close()
        await bot.session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="LikBy Service Runner")
    parser.add_argument("--mode", choices=["webhook", "polling"], default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    settings = get_settings()
    mode = args.mode or settings.bot_mode

    if mode == "polling":
        asyncio.run(run_polling())
    else:
        uvicorn.run("tikible.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
