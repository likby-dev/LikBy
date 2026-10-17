"""
likby.repositories.interfaces
Abstract repository interfaces decoupling domain services from persistence backends.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
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
from likby.domain.entities.subscription import SubscriptionEntitlement, SubscriptionPlan, ProviderPrice
from likby.domain.entities.payment import PaymentOrder, PaymentTransaction, UsageCounter, WebhookEventLedger, AuditEvent
from likby.domain.entities.referral import ReferralReward
from likby.domain.entities.daily_usage import DailyUsage
from likby.domain.entities.media_quota import MediaQuotaEvent
from likby.domain.entities.outbox import OutboxJob
from likby.domain.enums import FeatureKey, MediaQuotaStatus, MessageDeliveryStatus, PaymentProviderType



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

    async def save_event(
        self,
        session_id: str,
        event_id: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        display_text: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        sequence: Optional[int] = None,
    ) -> Any:
        return None

    async def get_session_events(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> List[Any]:
        return []


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

    @abstractmethod
    async def increment_upload(self, user_id: str, usage_date: str) -> int:
        pass

    @abstractmethod
    async def increment_received(self, user_id: str, usage_date: str) -> int:
        pass


class MediaQuotaEventRepository(ABC):
    @abstractmethod
    async def record_event(self, event: MediaQuotaEvent) -> bool:
        """Returns True if newly inserted, False if already exists (idempotency)."""
        pass

    @abstractmethod
    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[MediaQuotaEvent]:
        pass

    @abstractmethod
    async def get_user_events_today(self, user_id: str, date_str: str) -> List[MediaQuotaEvent]:
        pass

    @abstractmethod
    async def update_status(
        self,
        idempotency_key: str,
        status: MediaQuotaStatus,
        completed_at: Optional[datetime] = None,
    ) -> bool:
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


class SubscriptionPlanRepository(ABC):
    @abstractmethod
    async def get_all_active_plans(self) -> List[SubscriptionPlan]:
        pass

    @abstractmethod
    async def get_plan_by_code(self, code: str) -> Optional[SubscriptionPlan]:
        pass

    @abstractmethod
    async def get_prices_for_plan(self, plan_id: str, provider: Optional[PaymentProviderType] = None) -> List[ProviderPrice]:
        pass

    @abstractmethod
    async def get_price_by_id(self, price_id: str) -> Optional[ProviderPrice]:
        pass


class PaymentOrderRepository(ABC):
    @abstractmethod
    async def save(self, order: PaymentOrder) -> None:
        pass

    @abstractmethod
    async def get_by_id(self, order_id: str) -> Optional[PaymentOrder]:
        pass

    @abstractmethod
    async def get_by_internal_order_id(self, internal_order_id: str) -> Optional[PaymentOrder]:
        pass

    @abstractmethod
    async def get_by_provider_order_id(self, provider: PaymentProviderType, provider_order_id: str) -> Optional[PaymentOrder]:
        pass

    @abstractmethod
    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[PaymentOrder]:
        pass

    @abstractmethod
    async def get_user_orders(self, user_id: str, limit: int = 20) -> List[PaymentOrder]:
        pass


class PaymentTransactionRepository(ABC):
    @abstractmethod
    async def save(self, transaction: PaymentTransaction) -> None:
        pass

    @abstractmethod
    async def get_by_id(self, transaction_id: str) -> Optional[PaymentTransaction]:
        pass

    @abstractmethod
    async def get_by_provider_payment_id(self, provider_payment_id: str) -> Optional[PaymentTransaction]:
        pass

    @abstractmethod
    async def get_by_order_id(self, order_id: str) -> List[PaymentTransaction]:
        pass

    @abstractmethod
    async def list_by_user(self, user_id: str) -> List[PaymentTransaction]:
        pass


class UsageCounterRepository(ABC):
    @abstractmethod
    async def get_usage(self, user_id: str, feature_key: FeatureKey, period_start: str) -> int:
        pass

    @abstractmethod
    async def increment_usage(self, user_id: str, feature_key: FeatureKey, period_start: str, period_end: str, delta: int = 1) -> int:
        pass

    @abstractmethod
    async def get_user_daily_summary(self, user_id: str, date_str: str) -> dict:
        pass


class WebhookLedgerRepository(ABC):
    @abstractmethod
    async def record_event(self, event: WebhookEventLedger) -> bool:
        """Returns True if newly inserted, False if already exists (duplicate)."""
        pass

    @abstractmethod
    async def get_by_provider_event_id(self, provider: PaymentProviderType, provider_event_id: str) -> Optional[WebhookEventLedger]:
        pass


class AuditEventRepository(ABC):
    @abstractmethod
    async def record_event(self, event: AuditEvent) -> None:
        pass

    @abstractmethod
    async def get_events_for_entity(self, entity_type: str, entity_id: str) -> List[AuditEvent]:
        pass


class ReferralRewardRepository(ABC):
    @abstractmethod
    async def save(self, referral: ReferralReward) -> None:
        pass

    @abstractmethod
    async def get_by_invited_user_id(self, invited_user_id: str) -> Optional[ReferralReward]:
        pass

    @abstractmethod
    async def count_qualified_in_period(self, referrer_user_id: str, since: str) -> int:
        pass

    @abstractmethod
    async def get_user_referrals(self, referrer_user_id: str) -> List[ReferralReward]:
        pass


class PlayGameRepository(ABC):
    @abstractmethod
    async def save_session(self, session: "PlayGameSession") -> None:
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional["PlayGameSession"]:
        pass

    @abstractmethod
    async def add_participant(self, participant: "GameParticipant") -> None:
        pass

    @abstractmethod
    async def get_participants(self, session_id: str) -> List["GameParticipant"]:
        pass

    @abstractmethod
    async def save_invitation(self, invitation: "GameInvitation") -> None:
        pass

    @abstractmethod
    async def get_invitation(self, invitation_id: str) -> Optional["GameInvitation"]:
        pass

    @abstractmethod
    async def get_pending_invitations_for_user(self, user_id: str) -> List["GameInvitation"]:
        pass

    @abstractmethod
    async def record_action(
        self,
        action_id: str,
        session_id: str,
        user_id: str,
        action_type: str,
        payload: dict,
        sequence_num: int,
    ) -> None:
        pass

    @abstractmethod
    async def get_actions(self, session_id: str) -> List[dict]:
        pass

    @abstractmethod
    async def record_statistic(self, stat: "GameStatistic") -> None:
        pass

    @abstractmethod
    async def get_statistic(self, user_id: str, game_id: "GameType") -> Optional["GameStatistic"]:
        pass

    @abstractmethod
    async def get_user_statistics(self, user_id: str) -> List["GameStatistic"]:
        pass


class DuelQuotaRepository(ABC):
    @abstractmethod
    async def record_consumption(self, usage: "DuelQuotaUsage") -> bool:
        pass

    @abstractmethod
    async def count_duels_in_period(self, user_id: str, period_start: str) -> int:
        pass

    @abstractmethod
    async def has_consumed_for_session(self, user_id: str, session_id: str) -> bool:
        pass

