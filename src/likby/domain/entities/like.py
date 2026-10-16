"""
likby.domain.entities.like
Directional social interest (Like) entity.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class Like(BaseModel):
    """Directional like expressed by user_id towards target_id."""

    id: str = Field(..., description="Unique like identifier (lik_...)")
    sender_id: str = Field(..., description="User ID who expressed interest")
    target_id: str = Field(..., description="User ID who received interest")
    session_id: Optional[str] = Field(default=None, description="Optional chat session where like occurred")
    is_active: bool = Field(default=True, description="Whether the like is valid and unwithdrawn")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def withdraw(self) -> None:
        """Withdraw active like."""
        self.is_active = False
