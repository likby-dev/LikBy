"""
likby.domain.entities.session_event
Domain entity representing structured conversation lifecycle and system events.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SessionEvent(BaseModel):
    """Structured session lifecycle or system event stored in Firestore."""

    id: str = Field(..., description="Unique event identifier (evt_...)")
    session_id: str = Field(..., description="Foreign key to ChatSession.id")
    event_type: str = Field(..., description="Event classification, e.g. SESSION_REPORTED")
    actor_user_id: Optional[str] = Field(default=None, description="User ID who triggered event or None for SYSTEM")
    display_text: str = Field(..., description="Standardized human-readable text for transcript")
    sequence: int = Field(default=0, description="Authoritative ordering sequence within session")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Event metadata attributes")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def event_id(self) -> str:
        """Alias for id matching Firestore schema."""
        return self.id

    @property
    def sequence_number(self) -> int:
        """Alias for sequence matching Firestore schema."""
        return self.sequence
