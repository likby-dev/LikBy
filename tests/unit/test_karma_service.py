"""
tests.unit.test_karma_service
Unit tests for post-session ratings, auditable karma ledger, and score adjustments.
"""

from datetime import datetime, timezone
import pytest

from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.user import User
from likby.domain.enums import ChatSessionStatus, RatingType, UserState, UserStatus
from likby.repositories.sqlite.chat_session_repository import SqliteChatSessionRepository
from likby.repositories.sqlite.database import init_sqlite_db
from likby.repositories.sqlite.karma_repository import SqliteKarmaRepository
from likby.repositories.sqlite.rating_repository import SqliteRatingRepository
from likby.repositories.sqlite.user_repository import SqliteUserRepository
from likby.services.karma_service import KarmaService


@pytest.mark.asyncio
async def test_session_rating_and_karma_lifecycle(tmp_path):
    """Test session rating, reversing old contribution, and audit ledger entries."""
    db_file = tmp_path / "test_karma.db"
    conn = await init_sqlite_db(str(db_file))

    user_repo = SqliteUserRepository(conn)
    session_repo = SqliteChatSessionRepository(conn)
    rating_repo = SqliteRatingRepository(conn)
    karma_repo = SqliteKarmaRepository(conn)

    service = KarmaService(
        rating_repo=rating_repo,
        karma_repo=karma_repo,
        user_repo=user_repo,
        session_repo=session_repo,
    )

    # 1. Setup users and session
    u1 = User(id="usr_rater", telegram_id=111, karma_score=100)
    u2 = User(id="usr_ratee", telegram_id=222, karma_score=100)
    await user_repo.save(u1)
    await user_repo.save(u2)

    session = ChatSession(
        id="cs_karma_01",
        user_a_id="usr_rater",
        user_b_id="usr_ratee",
        status=ChatSessionStatus.ENDED,
    )
    await session_repo.save(session)

    # 2. Self-rating rejected
    success, msg, _ = await service.rate_session(
        session_id=session.id,
        rater_id="usr_rater",
        rating_type=RatingType.LIKE,
    )
    assert success is True
    # Verify ratee received +1
    u2_updated = await user_repo.get_by_id("usr_ratee")
    assert u2_updated.karma_score == 101

    # 3. Duplicate rating rejected with 0 delta
    dup_success, dup_msg, _ = await service.rate_session(
        session_id=session.id,
        rater_id="usr_rater",
        rating_type=RatingType.LIKE,
    )
    assert dup_success is False
    assert "already submitted" in dup_msg

    # 4. Modifying rating from LIKE to DISLIKE reverses +1 and applies -1 (net -2)
    mod_success, mod_msg, mod_delta = await service.rate_session(
        session_id=session.id,
        rater_id="usr_rater",
        rating_type=RatingType.DISLIKE,
    )
    assert mod_success is True
    assert mod_delta == -2

    u2_final = await user_repo.get_by_id("usr_ratee")
    assert u2_final.karma_score == 99

    # 5. Check ledger audit entries
    summary = await service.get_user_karma_summary("usr_ratee")
    assert summary["karma_score"] == 99
    assert len(summary["ledger"]) == 2

    await conn.close()
