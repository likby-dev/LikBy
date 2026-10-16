"""
likby.domain.entities.rating
Post-session participant evaluation rating entity.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, Field
from likby.domain.enums import RatingType


class SessionRating(BaseModel):
    """Post-chat participant evaluation."""

    id: str = Field(..., description="Unique rating ID (rat_...)")
    session_id: str = Field(..., description="Foreign key to ChatSession.id")
    rater_id: str = Field(..., description="User ID submitting the rating")
    ratee_id: str = Field(..., description="User ID receiving the rating")
    rating: RatingType = Field(..., description="LIKE (+1 karma) or DISLIKE (-1 karma)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, session_id: str, rater_id: str, ratee_id: str, rating: RatingType) -> "SessionRating":
        """Instantiate rating, enforcing non-self rating."""
        if rater_id == ratee_id:
            raise ValueError("Users cannot rate themselves.")
        return cls(
            id=f"rat_{session_id}_{rater_id}",
            session_id=session_id,
            rater_id=rater_id,
            ratee_id=ratee_id,
            rating=rating,
            created_at=datetime.now(timezone.utc),
        )
