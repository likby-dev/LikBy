"""
tikible.repositories.interfaces
Abstract repository interfaces decoupling domain services from persistence backends.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from tikible.domain.entities.user import User
from tikible.domain.entities.profile import Profile
from tikible.domain.entities.match_ticket import MatchTicket
from tikible.domain.entities.chat_session import ChatSession
from tikible.domain.entities.game import GameSession
from tikible.domain.entities.report import Report
from tikible.domain.entities.block import UserBlock


class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[User]:
        pass

    @abstractmethod
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        pass

    @abstractmethod
    async def save(self, user: User) -> None:
        pass


class ProfileRepository(ABC):
    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> Optional[Profile]:
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
    async def get_report_count_for_user(self, reported_id: str) -> int:
        pass
