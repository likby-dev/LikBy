"""
likby.domain
Core domain entities, value objects, and business rules.
"""

from likby.domain.enums import (
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
from likby.domain.entities.user import User
from likby.domain.entities.profile import Profile
from likby.domain.entities.match_ticket import MatchTicket
from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.game import GameSession, InvalidMoveError, NotYourTurnError
from likby.domain.entities.report import Report
from likby.domain.entities.block import UserBlock
from likby.domain.matching.scorer import calculate_match_score

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
