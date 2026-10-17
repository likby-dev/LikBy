"""
likby.services.social_service
Directional likes, mutual-like matching, canonical friendships, and friend limits.
"""

from typing import List, Optional, Tuple
from likby.domain.entities.friendship import Friendship
from likby.domain.entities.like import Like
from likby.domain.enums import FriendshipStatus
from likby.repositories.interfaces import (
    BlockRepository,
    FriendshipRepository,
    LikeRepository,
    UserRepository,
)
from likby.services.subscription_service import SubscriptionService


class SocialService:
    """Manages directional social discovery, mutual likes, and canonical friendships."""

    def __init__(
        self,
        like_repo: LikeRepository,
        friendship_repo: FriendshipRepository,
        user_repo: UserRepository,
        block_repo: BlockRepository,
        subscription_service: SubscriptionService,
    ) -> None:
        self._like_repo = like_repo
        self._friendship_repo = friendship_repo
        self._user_repo = user_repo
        self._block_repo = block_repo
        self._subscription_service = subscription_service

    async def express_like(
        self,
        sender_id: str,
        target_id: str,
        session_id: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Friendship]]:
        """
        Record directional like. If reciprocal like exists, attempt atomic friendship creation
        subject to friend limit capacity checks.
        """
        if sender_id == target_id:
            return False, "Users cannot like themselves.", None

        # Check block status
        if await self._block_repo.is_blocked(sender_id, target_id):
            return False, "Interaction unavailable.", None

        # Check existing friendship
        existing_friendship = await self._friendship_repo.get_friendship(sender_id, target_id)
        if existing_friendship and existing_friendship.status == FriendshipStatus.ACTIVE:
            return True, "You are already friends with this user.", existing_friendship

        # Record directional like
        like_id = f"lik_{sender_id}_{target_id}"
        like = Like(
            id=like_id,
            sender_id=sender_id,
            target_id=target_id,
            session_id=session_id,
            is_active=True,
        )
        await self._like_repo.save(like)

        # Check reciprocal like
        reciprocal = await self._like_repo.get_like(sender_id=target_id, target_id=sender_id)
        if reciprocal and reciprocal.is_active:
            # Check capacity for sender
            sender_friends = await self._friendship_repo.count_user_friends(sender_id)
            if not await self._subscription_service.can_add_friend(sender_id, sender_friends):
                return (
                    True,
                    "Like recorded! You have reached your friend limit. Upgrade your subscription to connect.",
                    None,
                )

            # Check capacity for target
            target_friends = await self._friendship_repo.count_user_friends(target_id)
            if not await self._subscription_service.can_add_friend(target_id, target_friends):
                return (
                    True,
                    "Like recorded! Your partner has reached their friend limit.",
                    None,
                )

            # Both eligible: create atomic canonical friendship
            friendship = Friendship.create(sender_id, target_id, source="MUTUAL_LIKE")
            await self._friendship_repo.save(friendship)
            return True, "It's a match! You both liked each other and are now friends! 💙", friendship

        return True, "Like sent! If they like you back, you will become friends.", None

    async def get_who_liked_me(self, user_id: str) -> List[dict]:
        """
        Retrieve valid incoming likes where no friendship exists yet and user is not blocked.
        """
        incoming = await self._like_repo.get_incoming_likes(user_id)
        results = []

        for lk in incoming:
            # Verify sender is not blocked
            if await self._block_repo.is_blocked(user_id, lk.sender_id):
                continue

            # Verify no existing friendship
            f = await self._friendship_repo.get_friendship(user_id, lk.sender_id)
            if f and f.status == FriendshipStatus.ACTIVE:
                continue

            sender = await self._user_repo.get_by_id(lk.sender_id)
            if not sender:
                continue

            results.append({
                "like_id": lk.id,
                "sender_id": lk.sender_id,
                "sender_display_id": sender.display_user_id,
                "session_id": lk.session_id,
                "created_at": lk.created_at,
            })

        return results

    async def get_user_friends(self, user_id: str) -> List[dict]:
        """Retrieve active friends with display IDs."""
        friendships = await self._friendship_repo.get_user_friends(user_id)
        results = []

        for f in friendships:
            friend_id = f.get_friend_id(user_id)
            friend_user = await self._user_repo.get_by_id(friend_id)
            display_id = friend_user.display_user_id if friend_user else friend_id

            results.append({
                "friendship_id": f.id,
                "friend_user_id": friend_id,
                "display_id": display_id,
                "source": f.source,
                "since": f.created_at.strftime("%Y-%m-%d"),
            })

        return results

    async def remove_friend(self, user_id: str, friend_id: str) -> Tuple[bool, str]:
        """Remove an existing active friendship."""
        friendship = await self._friendship_repo.get_friendship(user_id, friend_id)
        if not friendship or friendship.status != FriendshipStatus.ACTIVE:
            return False, "Active friendship not found."

        friendship.remove()
        await self._friendship_repo.save(friendship)
        return True, "Friendship removed."

    async def can_add_friend(self, user_id: str) -> bool:
        """Check if user has remaining friend capacity according to their subscription tier."""
        limits = await self._subscription_service.get_plan_limits(user_id)
        max_friends = limits.get("max_friends", 3)
        current_friends = await self._friendship_repo.count_user_friends(user_id)
        return current_friends < max_friends
