"""
likby.domain.entities.chat_session
ChatSession domain entity representing an active anonymous conversation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, model_validator
from likby.domain.enums import SessionStatus, TerminationReason


class ChatSession(BaseModel):
    """Anonymous conversation session between two users."""

    id: str = Field(..., description="Unique session ID")
    user_a_id: str = Field(..., description="First user ID")
    user_b_id: str = Field(..., description="Second user ID")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, description="Session status")
    match_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Calculated compatibility")
    match_metadata: Dict[str, Any] = Field(default_factory=dict, description="Common interests & tags")
    message_count: int = Field(default=0, ge=0, description="Total messages relayed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    ended_by_user_id: Optional[str] = None
    termination_reason: Optional[TerminationReason] = None

    @model_validator(mode="after")
    def validate_different_users(self) -> "ChatSession":
        if self.user_a_id == self.user_b_id:
            raise ValueError("user_a_id and user_b_id must be different users")
        return self

    def get_partner_id(self, user_id: str) -> str:
        """Return the ID of the other user in this session."""
        if user_id == self.user_a_id:
            return self.user_b_id
        elif user_id == self.user_b_id:
            return self.user_a_id
        raise ValueError(f"User {user_id} is not a participant in session {self.id}")

    def record_message(self) -> None:
        """Register that a message was forwarded."""
        self.message_count += 1
        self.last_activity_at = datetime.now(timezone.utc)

    def is_silent_for(self, seconds: int) -> bool:
        """Check if session has had zero activity for more than given seconds."""
        delta = datetime.now(timezone.utc) - self.last_activity_at
        return delta.total_seconds() >= seconds

    def end(self, ended_by: Optional[str], reason: TerminationReason) -> None:
        """Terminate the chat session."""
        self.status = SessionStatus.ENDED
        self.ended_by_user_id = ended_by
        self.termination_reason = reason
        self.ended_at = datetime.now(timezone.utc)
