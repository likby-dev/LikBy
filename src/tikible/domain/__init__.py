"""
tikible.domain
Core domain entities, value objects, and business rules.
"""

from tikible.domain.enums import (
    Gender,
    GenderPreference,
    GameStatus,
    GameType,
    ReportCategory,
    ReportStatus,
    SessionStatus,
    TerminationReason,
    TicketStatus,
    UserState,
    UserStatus,
)
from tikible.domain.entities.user import User
from tikible.domain.entities.profile import Profile
from tikible.domain.entities.match_ticket import MatchTicket
from tikible.domain.entities.chat_session import ChatSession
from tikible.domain.entities.game import GameSession, InvalidMoveError, NotYourTurnError
from tikible.domain.entities.report import Report
from tikible.domain.entities.block import UserBlock
from tikible.domain.matching.scorer import calculate_match_score

__all__ = [
    "UserState",
    "UserStatus",
    "Gender",
    "GenderPreference",
    "TicketStatus",
    "SessionStatus",
    "TerminationReason",
    "GameType",
    "GameStatus",
    "ReportCategory",
    "ReportStatus",
    "User",
    "Profile",
    "MatchTicket",
    "ChatSession",
    "GameSession",
    "InvalidMoveError",
    "NotYourTurnError",
    "Report",
    "UserBlock",
    "calculate_match_score",
]
