"""
likby.domain.entities.payment
Entities representing payment orders, transactions, webhook events, and audit ledgers.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from likby.domain.enums import (
    FeatureKey,
    PaymentOrderStatus,
    PaymentProviderType,
    PaymentTransactionStatus,
    WebhookProcessingStatus,
)


class PaymentOrder(BaseModel):
    """Internal server-calculated payment order."""

    id: str = Field(..., description="Internal DB primary key e.g. ord_01K8...")
    internal_order_id: str = Field(..., description="Unique human-readable reference e.g. LIKBY-ORD-...")
    user_id: str = Field(..., description="Foreign key to User.id")
    plan_id: str = Field(..., description="Foreign key to SubscriptionPlan.id or tier code")
    provider: PaymentProviderType
    provider_order_id: Optional[str] = Field(default=None, description="External provider order ID e.g. order_K... from Razorpay")
    amount_minor_units: int = Field(..., description="Exact amount in paise for INR, integer count for XTR")
    currency: str = Field(..., description="INR or XTR")
    status: PaymentOrderStatus = Field(default=PaymentOrderStatus.CREATED)
    idempotency_key: Optional[str] = Field(default=None, description="Unique client/checkout idempotency token")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None


class PaymentTransaction(BaseModel):
    """Settled or captured financial transaction record."""

    id: str = Field(..., description="Transaction ID e.g. txn_01K8...")
    order_id: str = Field(..., description="Foreign key to PaymentOrder.id")
    provider: PaymentProviderType
    provider_payment_id: str = Field(..., description="External payment ID e.g. pay_K... from Razorpay or charge_id from Telegram")
    provider_order_id: Optional[str] = None
    provider_signature_verified: bool = Field(default=True)
    amount_minor_units: int
    currency: str
    payment_status: PaymentTransactionStatus = Field(default=PaymentTransactionStatus.CAPTURED)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UsageCounter(BaseModel):
    """Granular atomic quota consumption tracking."""

    id: str = Field(..., description="Counter ID e.g. use_01K8...")
    user_id: str = Field(..., description="Foreign key to User.id")
    feature_key: FeatureKey
    period_start: str = Field(..., description="Date string YYYY-MM-DD")
    period_end: str = Field(..., description="Date string YYYY-MM-DD")
    used: int = Field(default=0, ge=0)
    version: int = Field(default=1)


class WebhookEventLedger(BaseModel):
    """Immutable record of incoming provider webhook notifications for deduplication."""

    id: str = Field(..., description="Ledger ID e.g. whk_01K8...")
    provider: PaymentProviderType
    provider_event_id: Optional[str] = None
    event_type: str
    signature_verified: bool
    processing_status: WebhookProcessingStatus = Field(default=WebhookProcessingStatus.PROCESSED)
    payload_hash: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    safe_error_code: Optional[str] = None


class AuditEvent(BaseModel):
    """Append-only audit ledger entry for compliance and state tracking."""

    id: str = Field(..., description="Audit record ID e.g. aud_01K8...")
    actor_id: str = Field(..., description="User ID, SYSTEM, or ADMIN who initiated the action")
    event_type: str = Field(..., description="e.g. SUBSCRIPTION_ACTIVATED, PAYMENT_CAPTURED, REFUND_PROCESSED")
    entity_type: str = Field(..., description="e.g. PAYMENT_ORDER, SUBSCRIPTION, REFERRAL")
    entity_id: str = Field(..., description="ID of affected entity")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
