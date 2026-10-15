"""
tikible.telegram.bot
aiogram Dispatcher setup and router registration.
"""

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from tikible.config import Settings
from tikible.repositories.interfaces import (
    BlockRepository,
    ChatSessionRepository,
    GameRepository,
    MatchTicketRepository,
    ProfileRepository,
    ReportRepository,
    UserRepository,
)
from tikible.services.chat_relay_service import ChatRelayService
from tikible.services.matchmaking_service import MatchmakingService
from tikible.services.session_cache import ActiveSessionCache
from tikible.telegram.handlers import (
    chat,
    game,
    matchmaking,
    menu,
    onboarding,
    report,
    solo_games,
    start,
)


from aiogram.client.default import DefaultBotProperties


def create_bot(settings: Settings) -> Bot:
    """Instantiate aiogram Bot client with DefaultBotProperties."""
    return Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(
    user_repo: UserRepository,
    profile_repo: ProfileRepository,
    ticket_repo: MatchTicketRepository,
    session_repo: ChatSessionRepository,
    game_repo: GameRepository,
    block_repo: BlockRepository,
    report_repo: ReportRepository,
    session_cache: ActiveSessionCache,
    chat_relay: ChatRelayService,
    match_service: MatchmakingService,
) -> Dispatcher:
    """Create and configure aiogram Dispatcher with all routers and dependency injections."""
    dp = Dispatcher(storage=MemoryStorage())

    # Dependency injection into handler arguments
    dp["user_repo"] = user_repo
    dp["profile_repo"] = profile_repo
    dp["ticket_repo"] = ticket_repo
    dp["session_repo"] = session_repo
    dp["game_repo"] = game_repo
    dp["block_repo"] = block_repo
    dp["report_repo"] = report_repo
    dp["session_cache"] = session_cache
    dp["chat_relay"] = chat_relay
    dp["match_service"] = match_service

    routers = [
        start.router,
        onboarding.router,
        menu.router,
        matchmaking.router,
        game.router,
        solo_games.router,
        report.router,
        chat.router,
    ]
    for r in routers:
        r._parent_router = None
        dp.include_router(r)

    return dp
