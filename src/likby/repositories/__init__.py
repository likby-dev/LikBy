"""
likby.repositories
Persistence interfaces and repository implementations.
"""

from likby.repositories.interfaces import (
    BlockRepository,
    ChatSessionRepository,
    GameRepository,
    MatchTicketRepository,
    ProfileRepository,
    ReportRepository,
    UserRepository,
)
from likby.repositories.sqlite.database import init_sqlite_db
from likby.repositories.sqlite.user_repository import SqliteUserRepository
from likby.repositories.sqlite.profile_repository import SqliteProfileRepository
from likby.repositories.sqlite.match_ticket_repository import SqliteMatchTicketRepository
from likby.repositories.sqlite.chat_session_repository import SqliteChatSessionRepository
from likby.repositories.sqlite.game_repository import SqliteGameRepository
from likby.repositories.sqlite.block_repository import SqliteBlockRepository
from likby.repositories.sqlite.report_repository import SqliteReportRepository

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
