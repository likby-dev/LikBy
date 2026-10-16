"""
likby.domain.entities.karma
Auditable karma ledger entry entity.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from likby.domain.enums import KarmaSourceType


class KarmaLedgerEntry(BaseModel):
    """Immutable ledger record representing an atomic change in a user's karma."""

    id: str = Field(..., description="Unique karma event identifier (krm_...)")
    user_id: str = Field(..., description="User receiving the karma points delta")
    source_type: KarmaSourceType = Field(..., description="Classification of the event")
    reference_id: Optional[str] = Field(default=None, description="Related session ID or report ID")
    delta: int = Field(..., description="Points change (+1, -1, -15, etc.)")
    idempotency_key: str = Field(..., description="Deduplication key preventing duplicate points")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
