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


class TerminationReason(str, Enum):
    """Reason for chat session termination."""
    USER_STOPPED = "USER_STOPPED"
    USER_SKIPPED = "USER_SKIPPED"
    INACTIVITY_TIMEOUT = "INACTIVITY_TIMEOUT"
    USER_REPORTED = "USER_REPORTED"
    USER_BLOCKED = "USER_BLOCKED"
    ADMIN_OVERRIDE = "ADMIN_OVERRIDE"


class GameType(str, Enum):
    """Supported multiplayer game types."""
    TICTACTOE = "TICTACTOE"


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
    RESOLVED_NO_ACTION = "RESOLVED_NO_ACTION"
    RESOLVED_WARNED = "RESOLVED_WARNED"
    RESOLVED_BANNED = "RESOLVED_BANNED"
