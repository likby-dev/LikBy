"""
tests.unit.test_social_service
Unit tests for directional likes, mutual-like matching, friendships, and capacity enforcement.
"""

import pytest

from likby.domain.entities.user import User
from likby.domain.enums import FriendshipStatus
from likby.repositories.sqlite.block_repository import SqliteBlockRepository
from likby.repositories.sqlite.database import init_sqlite_db
from likby.repositories.sqlite.friendship_repository import SqliteFriendshipRepository
from likby.repositories.sqlite.like_repository import SqliteLikeRepository
from likby.repositories.sqlite.subscription_repository import SqliteSubscriptionRepository
from likby.repositories.sqlite.user_repository import SqliteUserRepository
from likby.services.social_service import SocialService
from likby.services.subscription_service import SubscriptionService


@pytest.mark.asyncio
async def test_mutual_like_friendship_and_capacity_limits(tmp_path):
    """Test directional like, reciprocal matching, canonical friendship, and friend limits."""
    db_file = tmp_path / "test_social.db"
    conn = await init_sqlite_db(str(db_file))

    user_repo = SqliteUserRepository(conn)
    like_repo = SqliteLikeRepository(conn)
    friendship_repo = SqliteFriendshipRepository(conn)
    block_repo = SqliteBlockRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)

    sub_service = SubscriptionService(sub_repo)
    social_service = SocialService(
        like_repo=like_repo,
        friendship_repo=friendship_repo,
        user_repo=user_repo,
        block_repo=block_repo,
        subscription_service=sub_service,
    )

    # Setup 4 users (User 1 will try to friend Users 2, 3, 4, 5)
    u1 = User(id="usr_01", telegram_id=101)
    u2 = User(id="usr_02", telegram_id=102)
    u3 = User(id="usr_03", telegram_id=103)
    u4 = User(id="usr_04", telegram_id=104)
    u5 = User(id="usr_05", telegram_id=105)

    for u in [u1, u2, u3, u4, u5]:
        await user_repo.save(u)

    # 1. User 1 likes User 2 -> unidirectional
    ok, msg, friendship = await social_service.express_like(u1.id, u2.id)
    assert ok is True
    assert friendship is None
    assert "If they like you back" in msg

    # Who liked User 2?
    incoming_u2 = await social_service.get_who_liked_me(u2.id)
    assert len(incoming_u2) == 1
    assert incoming_u2[0]["sender_id"] == u1.id

    # 2. User 2 likes User 1 back -> Mutual like forms canonical friendship
    ok2, msg2, friendship2 = await social_service.express_like(u2.id, u1.id)
    assert ok2 is True
    assert friendship2 is not None
    assert friendship2.id == "frd_usr_01_usr_02"
    assert friendship2.status == FriendshipStatus.ACTIVE

    # Mutual like removed from Who Liked Me once friendship exists
    incoming_u2_after = await social_service.get_who_liked_me(u2.id)
    assert len(incoming_u2_after) == 0

    # 3. Add 2 more friends for User 1 (reaching Free tier limit of 3)
    await social_service.express_like(u1.id, u3.id)
    await social_service.express_like(u3.id, u1.id)

    await social_service.express_like(u1.id, u4.id)
    await social_service.express_like(u4.id, u1.id)

    count_u1 = await friendship_repo.count_user_friends(u1.id)
    assert count_u1 == 3

    # 4. Attempt 4th friend for User 1 -> Blocked by capacity!
    await social_service.express_like(u5.id, u1.id)
    ok_cap, msg_cap, f_cap = await social_service.express_like(u1.id, u5.id)
    assert ok_cap is True
    assert f_cap is None
    assert "reached your friend limit" in msg_cap

    # 5. Remove a friend -> Capacity slot freed
    rem_ok, rem_msg = await social_service.remove_friend(u1.id, u2.id)
    assert rem_ok is True
    assert await friendship_repo.count_user_friends(u1.id) == 2

    await conn.close()
