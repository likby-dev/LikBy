"""
likby.repositories.supabase
Supabase REST-backed persistence implementations with automatic synchronization and SQLite fallback.
"""

from likby.repositories.supabase.user_repository import SupabaseUserRepository
from likby.repositories.supabase.profile_repository import SupabaseProfileRepository
from likby.repositories.supabase.chat_session_repository import SupabaseChatSessionRepository
from likby.repositories.supabase.like_repository import SupabaseLikeRepository
from likby.repositories.supabase.friendship_repository import SupabaseFriendshipRepository
from likby.repositories.supabase.connection_request_repository import SupabaseConnectionRequestRepository
from likby.repositories.supabase.rating_repository import SupabaseRatingRepository
from likby.repositories.supabase.karma_repository import SupabaseKarmaRepository
from likby.repositories.supabase.daily_usage_repository import SupabaseDailyUsageRepository
from likby.repositories.supabase.report_repository import SupabaseReportRepository

__all__ = [
    "SupabaseUserRepository",
    "SupabaseProfileRepository",
    "SupabaseChatSessionRepository",
    "SupabaseLikeRepository",
    "SupabaseFriendshipRepository",
    "SupabaseConnectionRequestRepository",
    "SupabaseRatingRepository",
    "SupabaseKarmaRepository",
    "SupabaseDailyUsageRepository",
    "SupabaseReportRepository",
]
