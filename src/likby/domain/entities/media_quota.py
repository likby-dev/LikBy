"""
likby.domain.entities.media_quota
Media quota event and accounting entity for idempotent, concurrency-safe limit enforcement.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from likby.domain.enums import MediaQuotaStatus, QuotaOperationType


class MediaQuotaEvent(BaseModel):
    """Auditable ledger entry for quota consumption events."""

    id: str = Field(..., description="Unique event ID e.g. mqe_...")
    user_id: str = Field(..., description="Foreign key to User.id")
    media_file_id: str = Field(..., description="Telegram file_id or media identifier")
    operation_type: QuotaOperationType = Field(..., description="UPLOAD or RECEIVE")
    idempotency_key: str = Field(..., description="Unique operation hash preventing duplicate quota consumption")
    status: MediaQuotaStatus = Field(default=MediaQuotaStatus.COMMITTED, description="Reservation status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def mark_completed(self) -> None:
        self.status = MediaQuotaStatus.COMMITTED
        self.completed_at = datetime.now(timezone.utc)

    def mark_rolled_back(self) -> None:
        self.status = MediaQuotaStatus.ROLLED_BACK
        self.completed_at = datetime.now(timezone.utc)
