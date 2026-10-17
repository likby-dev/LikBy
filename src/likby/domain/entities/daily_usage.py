"""
likby.domain.entities.daily_usage
Daily quota usage tracking entity.
"""

from pydantic import BaseModel, Field


class DailyUsage(BaseModel):
    """Atomic daily consumption counter for quota-governed actions."""

    user_id: str = Field(..., description="User ID")
    usage_date: str = Field(..., description="Date string YYYY-MM-DD (UTC)")
    searches_count: int = Field(default=0, ge=0, description="ID searches performed today")
    requests_count: int = Field(default=0, ge=0, description="Connection requests sent today")
    uploads_count: int = Field(default=0, ge=0, description="Media items uploaded today")
    received_count: int = Field(default=0, ge=0, description="Media items received today")

    def increment_search(self) -> None:
        """Increment daily search counter."""
        self.searches_count += 1

    def increment_request(self) -> None:
        """Increment daily connection request counter."""
        self.requests_count += 1

    def increment_upload(self) -> None:
        """Increment daily media upload counter."""
        self.uploads_count += 1

    def increment_received(self) -> None:
        """Increment daily media receive counter."""
        self.received_count += 1

