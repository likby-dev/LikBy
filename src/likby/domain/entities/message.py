"""
likby.domain.entities.message
Chat message entity representing persisted conversational events and delivery state.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from likby.domain.enums import MessageDeliveryStatus, MessageType


class ChatMessage(BaseModel):
    """Individual durable chat message record."""

    id: str = Field(..., description="Unique collision-resistant message identifier (msg_...)")
    session_id: str = Field(..., description="Foreign key to ChatSession.id")
    sender_id: str = Field(..., description="Internal user ID of the author (or 'SYSTEM')")
    sender_display_id: str = Field(..., description="Human-readable sender handle or formatted ID")
    sequence: int = Field(..., ge=1, description="Deterministic strictly increasing sequence within session")
    message_type: MessageType = Field(default=MessageType.TEXT, description="Content classification")
    text: Optional[str] = Field(default=None, description="Message text or media caption")
    media_asset_id: Optional[str] = Field(default=None, description="Foreign key to MediaAsset.id")
    reply_to_message_id: Optional[str] = Field(default=None, description="Optional reply target message ID")
    telegram_message_id: Optional[int] = Field(default=None, description="Telegram message ID for delivery context")
    delivery_status: MessageDeliveryStatus = Field(
        default=MessageDeliveryStatus.PENDING,
        description="Durable delivery state",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_at: Optional[datetime] = None

    def mark_delivered(self, telegram_msg_id: Optional[int] = None) -> None:
        """Mark message as successfully delivered to peer."""
        self.delivery_status = MessageDeliveryStatus.DELIVERED
        self.delivered_at = datetime.now(timezone.utc)
        if telegram_msg_id:
            self.telegram_message_id = telegram_msg_id

    def mark_failed(self) -> None:
        """Mark message delivery as failed after retries."""
        self.delivery_status = MessageDeliveryStatus.FAILED
