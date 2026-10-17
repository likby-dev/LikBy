"""
likby.domain.enums
Domain enumerations representing entity states, statuses, and categories.
"""

from enum import Enum


class UserState(str, Enum):
    """User operational/conversational state."""
    ONBOARDING_AGE_GATE = "ONBOARDING_AGE_GATE"
    ONBOARDING_ALIAS = "ONBOARDING_ALIAS"
    ONBOARDING_UNIQUE_ID = "ONBOARDING_UNIQUE_ID"
    ONBOARDING_AGE = "ONBOARDING_AGE"
    ONBOARDING_GENDER = "ONBOARDING_GENDER"
    ONBOARDING_INTERESTS = "ONBOARDING_INTERESTS"
    MAIN_MENU = "MAIN_MENU"
    IN_QUEUE = "IN_QUEUE"
    IN_CHAT = "IN_CHAT"
    IN_GAME = "IN_GAME"


class UserStatus(str, Enum):
    """Administrative user standing."""
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    BANNED = "BANNED"
    DELETED = "DELETED"


class Gender(str, Enum):
    """Gender identities."""
    MALE = "MALE"
    FEMALE = "FEMALE"
    NON_BINARY = "NON_BINARY"
    PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY"


class GenderPreference(str, Enum):
    """Partner gender preference filters."""
    ANY = "ANY"
    MALE = "MALE"
    FEMALE = "FEMALE"
    NON_BINARY = "NON_BINARY"


class TicketStatus(str, Enum):
    """Matchmaking queue ticket status."""
    WAITING = "WAITING"
    MATCHED = "MATCHED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class SessionStatus(str, Enum):
    """Chat session status."""
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    REPORTED = "REPORTED"


ChatSessionStatus = SessionStatus



class TerminationReason(str, Enum):
    """Reason for chat session termination."""
    USER_STOPPED = "USER_STOPPED"
    USER_SKIPPED = "USER_SKIPPED"
    INACTIVITY_TIMEOUT = "INACTIVITY_TIMEOUT"
    USER_REPORTED = "USER_REPORTED"
    USER_BLOCKED = "USER_BLOCKED"
    ADMIN_OVERRIDE = "ADMIN_OVERRIDE"


class GameType(str, Enum):
    """Supported multiplayer and solo game types in LikBy Play."""
    # Legacy
    TICTACTOE = "TICTACTOE"
    
    # 11 Multiplayer Duel Games
    CARROM_CLASH = "carrom_clash"
    AIR_RUSH = "air_rush"
    POCKET_POOL = "pocket_pool"
    STICK_ARENA = "stick_arena"
    QUICKDRAW = "quickdraw"
    WORD_RUSH = "word_rush"
    BRAIN_BLITZ = "brain_blitz"
    REFLEX_RUSH = "reflex_rush"
    CONNECT_FOUR = "connect_four"
    MINDMATCH = "mindmatch"
    MYSTERY_MISSION = "mystery_mission"

    # 6 Solo Games
    ZEN_MERGE = "zen_merge"
    WORD_HUNT = "word_hunt"
    COLOR_FLOW = "color_flow"
    POCKET_GOLF = "pocket_golf"
    REFLEX_LAB = "reflex_lab"
    DAILY_MYSTERY = "daily_mystery"


class GameMode(str, Enum):
    """Mode of game participation."""
    DUEL = "DUEL"
    SOLO = "SOLO"
    COOP_DUEL = "COOP_DUEL"


class PlaySessionStatus(str, Enum):
    """Multiplayer and solo session state machine."""
    CREATED = "CREATED"
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    STARTING = "STARTING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    ABANDONED = "ABANDONED"


class GameInvitationStatus(str, Enum):
    """Duel challenge invitation state."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class DuelParticipantRole(str, Enum):
    """Participant role in game session."""
    HOST = "HOST"
    CHALLENGER = "CHALLENGER"
    SOLO_PLAYER = "SOLO_PLAYER"


class GameStatus(str, Enum):
    """Multiplayer game lifecycle status."""
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DRAW = "DRAW"
    FORFEITED = "FORFEITED"


class ReportCategory(str, Enum):
    """Abuse and safety report categories."""
    NSFW = "NSFW"
    HARASSMENT = "HARASSMENT"
    SPAM = "SPAM"
    UNDERAGE = "UNDERAGE"
    OTHER = "OTHER"


class ReportStatus(str, Enum):
    """Moderation report review status."""
    PENDING = "PENDING"
    PENDING_REVIEW = "PENDING_REVIEW"
    REVIEWING = "REVIEWING"
    ACTIONED = "ACTIONED"
    DISMISSED = "DISMISSED"
    RESOLVED_NO_ACTION = "RESOLVED_NO_ACTION"
    RESOLVED_WARNED = "RESOLVED_WARNED"
    RESOLVED_BANNED = "RESOLVED_BANNED"


class MessageType(str, Enum):
    """Content classification for chat messages."""
    TEXT = "TEXT"
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    VOICE = "VOICE"
    DOCUMENT = "DOCUMENT"
    STICKER = "STICKER"
    SYSTEM = "SYSTEM"


class MessageDeliveryStatus(str, Enum):
    """Durable delivery states for outbound relay."""
    PENDING = "PENDING"
    SENDING = "SENDING"
    DELIVERED = "DELIVERED"
    RETRYING = "RETRYING"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class MediaUploadStatus(str, Enum):
    """Media object archival lifecycle."""
    PENDING = "PENDING"
    UPLOADING = "UPLOADING"
    ARCHIVED = "ARCHIVED"
    FAILED = "FAILED"


class RatingType(str, Enum):
    """Post-session evaluation rating."""
    LIKE = "LIKE"
    DISLIKE = "DISLIKE"


class KarmaSourceType(str, Enum):
    """Source event triggering a karma ledger change."""
    SESSION_RATING = "SESSION_RATING"
    SESSION_LIKE = "SESSION_LIKE"
    SESSION_DISLIKE = "SESSION_DISLIKE"
    MODERATION_PENALTY = "MODERATION_PENALTY"
    ADMIN_ADJUSTMENT = "ADMIN_ADJUSTMENT"


class FriendshipStatus(str, Enum):
    """Canonical friendship standing."""
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    REMOVED = "REMOVED"
    PENDING_CAPACITY = "PENDING_CAPACITY"


class ConnectionRequestStatus(str, Enum):
    """ID search connection request lifecycle."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"


class PresenceStatus(str, Enum):
    """User presence and activity visibility."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    HIDDEN = "HIDDEN"


class SubscriptionTier(str, Enum):
    """Authoritative subscription plan levels."""
    BASE = "BASE"
    SPARK = "SPARK"
    PREMIUM = "PREMIUM"
    DIAMOND = "DIAMOND"

    # Backward compatibility aliases
    FREE = "BASE"
    HIGHER = "DIAMOND"


class PaymentProviderType(str, Enum):
    """Authoritative payment provider types."""
    RAZORPAY = "RAZORPAY"
    TELEGRAM_STARS = "TELEGRAM_STARS"


class PaymentOrderStatus(str, Enum):
    """Lifecycle status of a payment order."""
    CREATED = "CREATED"
    PAID = "PAID"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    REFUNDED = "REFUNDED"


class PaymentTransactionStatus(str, Enum):
    """Payment transaction settlement status."""
    CAPTURED = "CAPTURED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


class EntitlementSource(str, Enum):
    """Source origin of an entitlement."""
    PURCHASE = "PURCHASE"
    PAYMENT = "PAYMENT"
    REFERRAL = "REFERRAL"
    ADMIN = "ADMIN"
    FREE = "FREE"


class EntitlementStatus(str, Enum):
    """Subscription entitlement active status."""
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    REVOKED = "REVOKED"


class WebhookProcessingStatus(str, Enum):
    """Webhook event processing outcome."""
    PROCESSED = "PROCESSED"
    DUPLICATE = "DUPLICATE"
    FAILED = "FAILED"
    IGNORED = "IGNORED"


class ReferralQualificationStatus(str, Enum):
    """Referral qualification state."""
    PENDING = "PENDING"
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"


class ReferralRewardStatus(str, Enum):
    """Referral reward disbursement status."""
    PENDING = "PENDING"
    REWARDED = "REWARDED"
    AWARDED = "AWARDED"
    CAP_REACHED = "CAP_REACHED"
    CAPPED = "CAPPED"


class FeatureKey(str, Enum):
    """Quota-governed feature keys."""
    LIKES = "LIKES"
    SEARCHES = "SEARCHES"
    REQUESTS = "REQUESTS"
    GAMES = "GAMES"
    BOOSTS = "BOOSTS"
    ICEBREAKERS = "ICEBREAKERS"
    UPLOADS = "UPLOADS"
    RECEIVED = "RECEIVED"
    DAILY_LIKES = "LIKES"
    DAILY_ID_LOOKUPS = "SEARCHES"
    DAILY_CONNECT_REQUESTS = "REQUESTS"
    DAILY_GAMES_STARTED = "GAMES"
    PROFILE_BOOSTS = "BOOSTS"
    DAILY_UPLOADS = "UPLOADS"
    DAILY_RECEIVED = "RECEIVED"


class QuotaOperationType(str, Enum):
    """Media quota event operation type."""
    UPLOAD = "UPLOAD"
    RECEIVE = "RECEIVE"


class MediaQuotaStatus(str, Enum):
    """Media quota event reservation lifecycle status."""
    RESERVED = "RESERVED"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"


class OutboxJobStatus(str, Enum):
    """Transactional outbox processing status."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    DEAD_LETTER = "DEAD_LETTER"
