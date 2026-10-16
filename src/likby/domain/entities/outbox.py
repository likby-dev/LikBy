"""
likby.domain.entities.outbox
Transactional outbox job entity for reliable asynchronous message delivery.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from likby.domain.enums import OutboxJobStatus


class OutboxJob(BaseModel):
    """Pending transactional delivery task."""

    id: str = Field(..., description="Unique job ID (job_...)")
    session_id: str = Field(..., description="Foreign key to ChatSession.id")
    message_id: str = Field(..., description="Foreign key to ChatMessage.id")
    recipient_tg_id: int = Field(..., description="Telegram user ID of message recipient")
    status: OutboxJobStatus = Field(default=OutboxJobStatus.PENDING, description="Execution status")
    attempts: int = Field(default=0, ge=0, description="Dispatch attempts made")
    max_attempts: int = Field(default=3, description="Maximum attempts before dead-lettering")
    last_error: Optional[str] = Field(default=None, description="Last recorded error string")
    next_attempt_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def record_attempt_failure(self, error: str, backoff_seconds: int = 5) -> None:
        """Increment attempt counter and compute backoff schedule."""
        self.attempts += 1
        self.last_error = error
        if self.attempts >= self.max_attempts:
            self.status = OutboxJobStatus.DEAD_LETTER
        else:
            self.status = OutboxJobStatus.PENDING
            self.next_attempt_at = datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp() + backoff_seconds,
                tz=timezone.utc,
            )

    def mark_completed(self) -> None:
        """Mark job as successfully processed."""
        self.status = OutboxJobStatus.COMPLETED
