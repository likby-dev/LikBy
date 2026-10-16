"""
likby.repositories
Persistence interfaces and repository implementations.
"""

from likby.repositories.interfaces import (
    BlockRepository,
    ChatSessionRepository,
    ConnectionRequestRepository,
    DailyUsageRepository,
    FriendshipRepository,
    GameRepository,
    KarmaRepository,
    LikeRepository,
    MatchTicketRepository,
    MediaAssetRepository,
    MessageRepository,
    OutboxRepository,
    ProfileRepository,
    RatingRepository,
    ReportRepository,
    SubscriptionRepository,
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
from likby.repositories.sqlite.message_repository import SqliteMessageRepository
from likby.repositories.sqlite.media_asset_repository import SqliteMediaAssetRepository
from likby.repositories.sqlite.like_repository import SqliteLikeRepository
from likby.repositories.sqlite.friendship_repository import SqliteFriendshipRepository
from likby.repositories.sqlite.connection_request_repository import SqliteConnectionRequestRepository
from likby.repositories.sqlite.rating_repository import SqliteRatingRepository
from likby.repositories.sqlite.karma_repository import SqliteKarmaRepository
from likby.repositories.sqlite.subscription_repository import SqliteSubscriptionRepository
from likby.repositories.sqlite.daily_usage_repository import SqliteDailyUsageRepository
from likby.repositories.sqlite.outbox_repository import SqliteOutboxRepository

__all__ = [
    "UserRepository",
    "ProfileRepository",
    "MatchTicketRepository",
    "ChatSessionRepository",
    "GameRepository",
    "BlockRepository",
    "ReportRepository",
    "MessageRepository",
    "MediaAssetRepository",
    "LikeRepository",
    "FriendshipRepository",
    "ConnectionRequestRepository",
    "RatingRepository",
    "KarmaRepository",
    "SubscriptionRepository",
    "DailyUsageRepository",
    "OutboxRepository",
    "init_sqlite_db",
    "SqliteUserRepository",
    "SqliteProfileRepository",
    "SqliteMatchTicketRepository",
    "SqliteChatSessionRepository",
    "SqliteGameRepository",
    "SqliteBlockRepository",
    "SqliteReportRepository",
    "SqliteMessageRepository",
    "SqliteMediaAssetRepository",
    "SqliteLikeRepository",
    "SqliteFriendshipRepository",
    "SqliteConnectionRequestRepository",
    "SqliteRatingRepository",
    "SqliteKarmaRepository",
    "SqliteSubscriptionRepository",
    "SqliteDailyUsageRepository",
    "SqliteOutboxRepository",
]
