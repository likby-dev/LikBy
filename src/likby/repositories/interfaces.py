"""
likby.repositories.interfaces
Abstract repository interfaces decoupling domain services from persistence backends.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from likby.domain.entities.user import User
from likby.domain.entities.profile import Profile
from likby.domain.entities.match_ticket import MatchTicket
from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.game import GameSession
from likby.domain.entities.report import Report
from likby.domain.entities.block import UserBlock
from likby.domain.entities.message import ChatMessage
from likby.domain.entities.media_asset import MediaAsset
from likby.domain.entities.like import Like
from likby.domain.entities.friendship import Friendship
from likby.domain.entities.connection_request import ConnectionRequest
from likby.domain.entities.rating import SessionRating
from likby.domain.entities.karma import KarmaLedgerEntry
from likby.domain.entities.subscription import SubscriptionEntitlement
from likby.domain.entities.daily_usage import DailyUsage
from likby.domain.entities.outbox import OutboxJob
from likby.domain.enums import MessageDeliveryStatus


class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[User]:
        pass

    @abstractmethod
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        pass

    @abstractmethod
    async def get_by_unique_id(self, unique_id: str) -> Optional[User]:
        pass

    @abstractmethod
    async def save(self, user: User) -> None:
        pass


class ProfileRepository(ABC):
    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> Optional[Profile]:
        pass

    @abstractmethod
    async def get_by_unique_id(self, unique_id: str) -> Optional[Profile]:
        pass

    @abstractmethod
    async def save(self, profile: Profile) -> None:
        pass


class MatchTicketRepository(ABC):
    @abstractmethod
    async def get_by_id(self, ticket_id: str) -> Optional[MatchTicket]:
        pass

    @abstractmethod
    async def get_active_by_user_id(self, user_id: str) -> Optional[MatchTicket]:
        pass

    @abstractmethod
    async def get_waiting_tickets(self, limit: int = 50) -> List[MatchTicket]:
        pass

    @abstractmethod
    async def save(self, ticket: MatchTicket) -> None:
        pass


class ChatSessionRepository(ABC):
    @abstractmethod
    async def get_by_id(self, session_id: str) -> Optional[ChatSession]:
        pass

    @abstractmethod
    async def get_active_by_user_id(self, user_id: str) -> Optional[ChatSession]:
        pass

    @abstractmethod
    async def save(self, session: ChatSession) -> None:
        pass


class GameRepository(ABC):
    @abstractmethod
    async def get_by_id(self, game_id: str) -> Optional[GameSession]:
        pass

    @abstractmethod
    async def get_active_by_session_id(self, session_id: str) -> Optional[GameSession]:
        pass

    @abstractmethod
    async def save(self, game: GameSession) -> None:
        pass


class BlockRepository(ABC):
    @abstractmethod
    async def is_blocked(self, user_a_id: str, user_b_id: str) -> bool:
        pass

    @abstractmethod
    async def save(self, block: UserBlock) -> None:
        pass


class ReportRepository(ABC):
    @abstractmethod
    async def save(self, report: Report) -> None:
        pass

    @abstractmethod
    async def get_by_id(self, report_id: str) -> Optional[Report]:
        pass

    @abstractmethod
    async def get_by_reported_user_id(self, reported_id: str) -> List[Report]:
        pass

    @abstractmethod
    async def get_report_count_for_user(self, reported_id: str) -> int:
        pass


class MessageRepository(ABC):
    @abstractmethod
    async def save(self, message: ChatMessage) -> None:
        pass

    @abstractmethod
    async def get_by_id(self, message_id: str) -> Optional[ChatMessage]:
        pass

    @abstractmethod
    async def get_session_messages(self, session_id: str, limit: int = 100, offset: int = 0) -> List[ChatMessage]:
        pass

    @abstractmethod
    async def get_next_sequence(self, session_id: str) -> int:
        pass

    @abstractmethod
    async def update_delivery_status(
        self,
        message_id: str,
        status: MessageDeliveryStatus,
        telegram_msg_id: Optional[int] = None,
    ) -> None:
        pass


class MediaAssetRepository(ABC):
    @abstractmethod
    async def save(self, asset: MediaAsset) -> None:
        pass

    @abstractmethod
    async def get_by_id(self, asset_id: str) -> Optional[MediaAsset]:
        pass

    @abstractmethod
    async def get_by_message_id(self, message_id: str) -> Optional[MediaAsset]:
        pass


class LikeRepository(ABC):
    @abstractmethod
    async def save(self, like: Like) -> None:
        pass

    @abstractmethod
    async def get_like(self, sender_id: str, target_id: str) -> Optional[Like]:
        pass

    @abstractmethod
    async def get_incoming_likes(self, target_id: str) -> List[Like]:
        pass


class FriendshipRepository(ABC):
    @abstractmethod
    async def save(self, friendship: Friendship) -> None:
        pass

    @abstractmethod
    async def get_by_id(self, friendship_id: str) -> Optional[Friendship]:
        pass

    @abstractmethod
    async def get_friendship(self, user_1: str, user_2: str) -> Optional[Friendship]:
        pass

    @abstractmethod
    async def get_user_friends(self, user_id: str) -> List[Friendship]:
        pass

    @abstractmethod
    async def count_user_friends(self, user_id: str) -> int:
        pass


class ConnectionRequestRepository(ABC):
    @abstractmethod
    async def save(self, request: ConnectionRequest) -> None:
        pass

    @abstractmethod
    async def get_by_id(self, request_id: str) -> Optional[ConnectionRequest]:
        pass

    @abstractmethod
    async def get_pending_between(self, sender_id: str, target_id: str) -> Optional[ConnectionRequest]:
        pass

    @abstractmethod
    async def get_incoming_requests(self, target_id: str) -> List[ConnectionRequest]:
        pass


class RatingRepository(ABC):
    @abstractmethod
    async def save(self, rating: SessionRating) -> None:
        pass

    @abstractmethod
    async def get_by_session_and_rater(self, session_id: str, rater_id: str) -> Optional[SessionRating]:
        pass


class KarmaRepository(ABC):
    @abstractmethod
    async def save_entry(self, entry: KarmaLedgerEntry) -> bool:
        pass

    @abstractmethod
    async def get_user_ledger(self, user_id: str, limit: int = 20) -> List[KarmaLedgerEntry]:
        pass

    @abstractmethod
    async def get_user_karma_score(self, user_id: str) -> int:
        pass


class SubscriptionRepository(ABC):
    @abstractmethod
    async def save(self, entitlement: SubscriptionEntitlement) -> None:
        pass

    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> Optional[SubscriptionEntitlement]:
        pass


class DailyUsageRepository(ABC):
    @abstractmethod
    async def get_or_create(self, user_id: str, usage_date: str) -> DailyUsage:
        pass

    @abstractmethod
    async def increment_search(self, user_id: str, usage_date: str) -> int:
        pass

    @abstractmethod
    async def increment_request(self, user_id: str, usage_date: str) -> int:
        pass


class OutboxRepository(ABC):
    @abstractmethod
    async def save(self, job: OutboxJob) -> None:
        pass

    @abstractmethod
    async def get_pending_jobs(self, limit: int = 20) -> List[OutboxJob]:
        pass

    @abstractmethod
    async def update_job(self, job: OutboxJob) -> None:
        pass
