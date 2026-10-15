"""
tikible.domain.entities.match_ticket
MatchTicket entity representing an active request in the matchmaking queue.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pydantic import BaseModel, Field
from tikible.domain.enums import Gender, GenderPreference, TicketStatus


class MatchTicket(BaseModel):
    """Temporary ticket placed in matchmaking queue by a seeking user."""

    id: str = Field(..., description="Unique ticket ID")
    user_id: str = Field(..., description="ID of seeking user")
    user_gender: Gender = Field(..., description="Gender of user")
    user_age: int = Field(..., description="Age of user")
    languages: List[str] = Field(default_factory=lambda: ["en"], description="User languages")
    interests: List[str] = Field(default_factory=list, description="User interest tags")
    preferred_genders: List[GenderPreference] = Field(
        default_factory=lambda: [GenderPreference.ANY],
        description="Target gender filter",
    )
    min_age: int = Field(default=18, description="Target minimum age")
    max_age: int = Field(default=99, description="Target maximum age")
    status: TicketStatus = Field(default=TicketStatus.WAITING, description="Ticket lifecycle state")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    matched_at: Optional[datetime] = None
    matched_user_id: Optional[str] = None
    session_id: Optional[str] = None
    lock_version: int = Field(default=1, description="Optimistic concurrency lock")

    @property
    def is_expired(self) -> bool:
        """Check if ticket has exceeded its 5-minute wait window."""
        return datetime.now(timezone.utc) >= self.expires_at

    def mark_matched(self, partner_user_id: str, session_id: str) -> None:
        """Transition ticket to matched status."""
        self.status = TicketStatus.MATCHED
        self.matched_user_id = partner_user_id
        self.session_id = session_id
        self.matched_at = datetime.now(timezone.utc)
        self.lock_version += 1

    def cancel(self) -> None:
        """Cancel ticket search."""
        self.status = TicketStatus.CANCELLED
        self.lock_version += 1
