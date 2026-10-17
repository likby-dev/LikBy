"""
likby.telegram.bot
aiogram Dispatcher setup and router registration with comprehensive dependency injection.
"""

from typing import Optional
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from likby.config import Settings
from likby.repositories.interfaces import (
    AuditEventRepository,
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
    MediaQuotaEventRepository,
    MessageRepository,
    OutboxRepository,
    PaymentOrderRepository,
    PaymentTransactionRepository,
    ProfileRepository,
    RatingRepository,
    ReferralRewardRepository,
    ReportRepository,
    SubscriptionPlanRepository,
    SubscriptionRepository,
    UsageCounterRepository,
    UserRepository,
    WebhookLedgerRepository,
)
from likby.services.audit_service import AuditService
from likby.services.chat_relay_service import ChatRelayService
from likby.services.discovery_service import DiscoveryService
from likby.services.gaming_entitlement_service import GamingEntitlementService
from likby.services.karma_service import KarmaService
from likby.services.matchmaking_service import MatchmakingService
from likby.services.media_quota_service import MediaQuotaService
from likby.services.media_storage_service import MediaService
from likby.services.payment_service import PaymentService
from likby.services.play_game_service import PlayGameService
from likby.services.referral_service import ReferralService
from likby.services.session_cache import ActiveSessionCache
from likby.services.social_service import SocialService
from likby.services.subscription_service import SubscriptionService
from likby.services.transcript_service import TranscriptService
from likby.services.usage_service import UsageService
from likby.telegram.handlers import (
    chat,
    game,
    matchmaking,
    menu,
    onboarding,
    payments,
    play,
    report,
    solo_games,
    start,
)


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
    message_repo: Optional[MessageRepository] = None,
    media_repo: Optional[MediaAssetRepository] = None,
    like_repo: Optional[LikeRepository] = None,
    friendship_repo: Optional[FriendshipRepository] = None,
    request_repo: Optional[ConnectionRequestRepository] = None,
    rating_repo: Optional[RatingRepository] = None,
    karma_repo: Optional[KarmaRepository] = None,
    subscription_repo: Optional[SubscriptionRepository] = None,
    daily_usage_repo: Optional[DailyUsageRepository] = None,
    outbox_repo: Optional[OutboxRepository] = None,
    media_service: Optional[MediaService] = None,
    transcript_service: Optional[TranscriptService] = None,
    karma_service: Optional[KarmaService] = None,
    social_service: Optional[SocialService] = None,
    discovery_service: Optional[DiscoveryService] = None,
    subscription_service: Optional[SubscriptionService] = None,
    plan_repo: Optional[SubscriptionPlanRepository] = None,
    order_repo: Optional[PaymentOrderRepository] = None,
    txn_repo: Optional[PaymentTransactionRepository] = None,
    usage_counter_repo: Optional[UsageCounterRepository] = None,
    webhook_ledger_repo: Optional[WebhookLedgerRepository] = None,
    audit_repo: Optional[AuditEventRepository] = None,
    referral_repo: Optional[ReferralRewardRepository] = None,
    usage_service: Optional[UsageService] = None,
    payment_service: Optional[PaymentService] = None,
    referral_service: Optional[ReferralService] = None,
    audit_service: Optional[AuditService] = None,
    gaming_entitlement_service: Optional[GamingEntitlementService] = None,
    play_game_service: Optional[PlayGameService] = None,
    media_quota_repo: Optional[MediaQuotaEventRepository] = None,
    media_quota_service: Optional[MediaQuotaService] = None,
) -> Dispatcher:
    """Create and configure aiogram Dispatcher with all routers and dependency injections."""
    dp = Dispatcher(storage=MemoryStorage())

    # Core Repositories
    dp["user_repo"] = user_repo
    dp["profile_repo"] = profile_repo
    dp["ticket_repo"] = ticket_repo
    dp["session_repo"] = session_repo
    dp["game_repo"] = game_repo
    dp["block_repo"] = block_repo
    dp["report_repo"] = report_repo

    # Social, Media & Subscription Repositories
    dp["message_repo"] = message_repo
    dp["media_repo"] = media_repo
    dp["media_quota_repo"] = media_quota_repo
    dp["like_repo"] = like_repo
    dp["friendship_repo"] = friendship_repo
    dp["request_repo"] = request_repo
    dp["rating_repo"] = rating_repo
    dp["karma_repo"] = karma_repo
    dp["subscription_repo"] = subscription_repo
    dp["daily_usage_repo"] = daily_usage_repo
    dp["outbox_repo"] = outbox_repo

    # Payment, Usage & Referral Repositories
    dp["plan_repo"] = plan_repo
    dp["order_repo"] = order_repo
    dp["txn_repo"] = txn_repo
    dp["usage_counter_repo"] = usage_counter_repo
    dp["webhook_ledger_repo"] = webhook_ledger_repo
    dp["audit_repo"] = audit_repo
    dp["referral_repo"] = referral_repo

    # Services
    dp["session_cache"] = session_cache
    dp["chat_relay"] = chat_relay
    dp["match_service"] = match_service
    dp["media_service"] = media_service
    dp["media_quota_service"] = media_quota_service
    dp["transcript_service"] = transcript_service
    dp["karma_service"] = karma_service
    dp["social_service"] = social_service
    dp["discovery_service"] = discovery_service
    dp["subscription_service"] = subscription_service
    dp["usage_service"] = usage_service
    dp["payment_service"] = payment_service
    dp["referral_service"] = referral_service
    dp["audit_service"] = audit_service
    dp["gaming_entitlement_service"] = gaming_entitlement_service
    dp["play_game_service"] = play_game_service

    routers = [
        start.router,
        onboarding.router,
        menu.router,
        payments.router,
        play.router,
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
