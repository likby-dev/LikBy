"""
tikible.repositories
Persistence interfaces and repository implementations.
"""

from tikible.repositories.interfaces import (
    BlockRepository,
    ChatSessionRepository,
    GameRepository,
    MatchTicketRepository,
    ProfileRepository,
    ReportRepository,
    UserRepository,
)
from tikible.repositories.sqlite.database import init_sqlite_db
from tikible.repositories.sqlite.user_repository import SqliteUserRepository
from tikible.repositories.sqlite.profile_repository import SqliteProfileRepository
from tikible.repositories.sqlite.match_ticket_repository import SqliteMatchTicketRepository
from tikible.repositories.sqlite.chat_session_repository import SqliteChatSessionRepository
from tikible.repositories.sqlite.game_repository import SqliteGameRepository
from tikible.repositories.sqlite.block_repository import SqliteBlockRepository
from tikible.repositories.sqlite.report_repository import SqliteReportRepository

__all__ = [
    "UserRepository",
    "ProfileRepository",
    "MatchTicketRepository",
    "ChatSessionRepository",
    "GameRepository",
    "BlockRepository",
    "ReportRepository",
    "init_sqlite_db",
    "SqliteUserRepository",
    "SqliteProfileRepository",
    "SqliteMatchTicketRepository",
    "SqliteChatSessionRepository",
    "SqliteGameRepository",
    "SqliteBlockRepository",
    "SqliteReportRepository",
]
