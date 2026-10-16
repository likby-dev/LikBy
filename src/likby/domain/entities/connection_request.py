"""
likby.domain.entities.connection_request
Discovery connection request entity.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from likby.domain.enums import ConnectionRequestStatus


class ConnectionRequest(BaseModel):
    """Explicit connection invitation initiated via User ID search."""

    id: str = Field(..., description="Unique connection request ID (req_...)")
    sender_id: str = Field(..., description="User ID issuing the request")
    target_id: str = Field(..., description="Target user ID receiving the request")
    status: ConnectionRequestStatus = Field(
        default=ConnectionRequestStatus.PENDING,
        description="Request lifecycle state",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def accept(self) -> None:
        """Accept pending request."""
        self.status = ConnectionRequestStatus.ACCEPTED
        self.resolved_at = datetime.now(timezone.utc)

    def reject(self) -> None:
        """Reject pending request."""
        self.status = ConnectionRequestStatus.REJECTED
        self.resolved_at = datetime.now(timezone.utc)

    def withdraw(self) -> None:
        """Cancel pending request."""
        self.status = ConnectionRequestStatus.WITHDRAWN
        self.resolved_at = datetime.now(timezone.utc)
