"""
tikible.domain.entities.report
User report domain entity for abuse handling.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from tikible.domain.enums import ReportCategory, ReportStatus


class Report(BaseModel):
    """User moderation report."""

    id: str = Field(..., description="Unique report ID")
    reporter_id: str = Field(..., description="ID of complaining user")
    reported_id: str = Field(..., description="ID of accused user")
    session_id: Optional[str] = Field(default=None, description="Related chat session ID")
    category: ReportCategory = Field(..., description="Abuse category")
    reason: str = Field(..., min_length=3, max_length=500, description="User explanation")
    evidence_snippet: Optional[str] = Field(default=None, max_length=1000)
    status: ReportStatus = Field(default=ReportStatus.PENDING, description="Moderation status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    action_taken: Optional[str] = None
