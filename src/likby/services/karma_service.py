"""
likby.services.karma_service
Post-session ratings, auditable karma ledger, and reputation adjustments.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple
import uuid

from likby.domain.entities.karma import KarmaLedgerEntry
from likby.domain.entities.rating import SessionRating
from likby.domain.enums import KarmaSourceType, RatingType
from likby.repositories.interfaces import (
    ChatSessionRepository,
    KarmaRepository,
    RatingRepository,
    UserRepository,
)


class KarmaService:
    """Manages post-session ratings and auditable karma ledger entries."""

    def __init__(
        self,
        rating_repo: RatingRepository,
        karma_repo: KarmaRepository,
        user_repo: UserRepository,
        session_repo: ChatSessionRepository,
    ) -> None:
        self._rating_repo = rating_repo
        self._karma_repo = karma_repo
        self._user_repo = user_repo
        self._session_repo = session_repo

    async def rate_session(
        self,
        session_id: str,
        rater_id: str,
        rating_type: RatingType,
    ) -> Tuple[bool, str, int]:
        """
        Record post-session rating and apply idempotent karma delta to partner.
        Returns: (success, message, delta_applied)
        """
        session = await self._session_repo.get_by_id(session_id)
        if not session:
            return False, "Session not found.", 0

        # Verify rater was participant and identify ratee
        if rater_id == session.user_a_id:
            ratee_id = session.user_b_id
        elif rater_id == session.user_b_id:
            ratee_id = session.user_a_id
        else:
            return False, "User was not a participant in this session.", 0

        if rater_id == ratee_id:
            return False, "Users cannot rate themselves.", 0

        ratee_user = await self._user_repo.get_by_id(ratee_id)
        if not ratee_user:
            return False, "Ratee account not found.", 0

        existing_rating = await self._rating_repo.get_by_session_and_rater(session_id, rater_id)

        target_delta = 1 if rating_type == RatingType.LIKE else -1

        if existing_rating:
            if existing_rating.rating == rating_type:
                return False, f"You have already submitted a {rating_type.value} for this session.", 0

            # Reversing old rating contribution
            old_delta = 1 if existing_rating.rating == RatingType.LIKE else -1
            effective_delta = target_delta - old_delta  # e.g., (+1) - (-1) = +2

            # Update rating record
            existing_rating.rating = rating_type
            await self._rating_repo.save(existing_rating)

            idempotency_key = f"rat_mod_{session_id}_{rater_id}_{rating_type.value}"
        else:
            effective_delta = target_delta
            new_rating = SessionRating.create(
                session_id=session_id,
                rater_id=rater_id,
                ratee_id=ratee_id,
                rating=rating_type,
            )
            await self._rating_repo.save(new_rating)
            idempotency_key = f"rat_{session_id}_{rater_id}_{rating_type.value}"

        # 3. Create immutable ledger entry
        ledger_entry = KarmaLedgerEntry(
            id=f"krm_{uuid.uuid4().hex[:12]}",
            user_id=ratee_id,
            source_type=KarmaSourceType.SESSION_RATING,
            reference_id=session_id,
            delta=effective_delta,
            idempotency_key=idempotency_key,
            created_at=datetime.now(timezone.utc),
        )
        saved = await self._karma_repo.save_entry(ledger_entry)

        if saved:
            # Update user aggregate karma score
            ratee_user.apply_karma_delta(effective_delta)
            await self._user_repo.save(ratee_user)

        action = "Like (+1)" if rating_type == RatingType.LIKE else "Dislike (-1)"
        return True, f"Session rated: {action}", effective_delta

    async def get_user_karma_summary(self, user_id: str) -> dict:
        """Get user karma standing and recent ledger entries."""
        user = await self._user_repo.get_by_id(user_id)
        ledger = await self._karma_repo.get_user_ledger(user_id, limit=20)
        score = user.karma_score if user else 100

        return {
            "user_id": user_id,
            "karma_score": score,
            "ledger": [
                {
                    "id": entry.id,
                    "source": entry.source_type.value,
                    "delta": entry.delta,
                    "created_at": entry.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                }
                for entry in ledger
            ],
        }
