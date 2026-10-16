"""
likby.domain.entities.friendship
Canonical bidirectional friendship entity.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, Field
from likby.domain.enums import FriendshipStatus


class Friendship(BaseModel):
    """Canonical bidirectional friendship record."""

    id: str = Field(..., description="Canonical key: frd_{min(u1, u2)}_{max(u1, u2)}")
    user_a_id: str = Field(..., description="Alphabetically smaller user ID")
    user_b_id: str = Field(..., description="Alphabetically larger user ID")
    status: FriendshipStatus = Field(default=FriendshipStatus.ACTIVE, description="Friendship standing")
    source: str = Field(default="MUTUAL_LIKE", description="Origin (MUTUAL_LIKE, CONNECTION_REQUEST)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, user_1: str, user_2: str, source: str = "MUTUAL_LIKE") -> "Friendship":
        """Instantiate canonical pair preventing duplicate representation."""
        if user_1 == user_2:
            raise ValueError("Users cannot form a friendship with themselves.")
        u_a, u_b = sorted([user_1, user_2])
        canonical_id = f"frd_{u_a}_{u_b}"
        now = datetime.now(timezone.utc)
        return cls(
            id=canonical_id,
            user_a_id=u_a,
            user_b_id=u_b,
            status=FriendshipStatus.ACTIVE,
            source=source,
            created_at=now,
            updated_at=now,
        )

    def get_friend_id(self, my_user_id: str) -> str:
        """Resolve partner user ID given one participant's ID."""
        if my_user_id == self.user_a_id:
            return self.user_b_id
        if my_user_id == self.user_b_id:
            return self.user_a_id
        raise ValueError(f"User {my_user_id} is not part of friendship {self.id}")

    def remove(self) -> None:
        """Mark friendship as removed."""
        self.status = FriendshipStatus.REMOVED
        self.updated_at = datetime.now(timezone.utc)

    def block(self) -> None:
        """Mark friendship as severed due to block."""
        self.status = FriendshipStatus.BLOCKED
        self.updated_at = datetime.now(timezone.utc)
