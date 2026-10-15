"""
likby.domain.entities.block
UserBlock domain entity establishing bilateral matching barriers.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, Field, model_validator


class UserBlock(BaseModel):
    """Pairwise block preventing matching between two users."""

    id: str = Field(..., description="Unique block ID")
    blocker_id: str = Field(..., description="User creating the block")
    blocked_id: str = Field(..., description="User being blocked")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_not_blocking_self(self) -> "UserBlock":
        if self.blocker_id == self.blocked_id:
            raise ValueError("Users cannot block themselves")
        return self
