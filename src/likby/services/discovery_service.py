"""
likby.services.discovery_service
User ID discovery, daily quota enforcement, and connection request lifecycle.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid

from likby.domain.entities.connection_request import ConnectionRequest
from likby.domain.entities.friendship import Friendship
from likby.domain.enums import ConnectionRequestStatus, FriendshipStatus, PresenceStatus
from likby.repositories.interfaces import (
    BlockRepository,
    ConnectionRequestRepository,
    DailyUsageRepository,
    FriendshipRepository,
    UserRepository,
)
from likby.services.subscription_service import SubscriptionService


class DiscoveryService:
    """Manages user discovery, quota-governed ID searches, and connection requests."""

    def __init__(
        self,
        user_repo: UserRepository,
        daily_usage_repo: DailyUsageRepository,
        connection_request_repo: ConnectionRequestRepository,
        friendship_repo: FriendshipRepository,
        block_repo: BlockRepository,
        subscription_service: SubscriptionService,
    ) -> None:
        self._user_repo = user_repo
        self._daily_usage_repo = daily_usage_repo
        self._request_repo = connection_request_repo
        self._friendship_repo = friendship_repo
        self._block_repo = block_repo
        self._subscription_service = subscription_service

    async def search_user(
        self,
        requester_id: str,
        query: str,
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        Execute quota-governed ID search with privacy preservation.
        Returns: (success, message, user_preview_dict)
        """
        clean_query = query.strip()
        if clean_query.startswith("@"):
            clean_query = clean_query[1:].strip()

        if not clean_query:
            return False, "Please provide a valid user handle or ID.", None

        # 1. Enforce daily search allowance
        ent = await self._subscription_service.get_or_create_entitlement(requester_id)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        usage = await self._daily_usage_repo.get_or_create(requester_id, today)

        if usage.searches_count >= ent.daily_searches_limit:
            return (
                False,
                f"Daily search quota reached ({ent.daily_searches_limit}/{ent.daily_searches_limit}). "
                "Upgrade to Premium to unlock more searches.",
                None,
            )

        # Count this search against daily quota
        await self._daily_usage_repo.increment_search(requester_id, today)

        # 2. Look up target account
        target_user = await self._user_repo.get_by_unique_id(clean_query.lower())
        if not target_user:
            target_user = await self._user_repo.get_by_id(clean_query)

        if not target_user:
            return False, "No user found with that ID or handle.", None

        if target_user.id == requester_id:
            return False, "You cannot search for your own profile.", None

        # 3. Privacy and block check
        if await self._block_repo.is_blocked(requester_id, target_user.id):
            return False, "No user found with that ID or handle.", None

        # 4. Check existing friendship
        existing_f = await self._friendship_repo.get_friendship(requester_id, target_user.id)
        is_friend = existing_f is not None and existing_f.status == FriendshipStatus.ACTIVE

        # 5. Check pending connection request
        pending_req = await self._request_repo.get_pending_between(requester_id, target_user.id)

        # 6. Evaluate coarse activity presence
        if target_user.presence == PresenceStatus.HIDDEN:
            presence_str = "Hidden"
        else:
            diff_hours = (datetime.now(timezone.utc) - target_user.last_active_at).total_seconds() / 3600
            presence_str = "Active recently" if diff_hours < 24 else "Inactive"

        preview = {
            "user_id": target_user.id,
            "display_id": target_user.display_user_id,
            "presence": presence_str,
            "is_friend": is_friend,
            "has_pending_request": pending_req is not None,
            "pending_request_id": pending_req.id if pending_req else None,
        }
        return True, "User found.", preview

    async def send_connection_request(
        self,
        sender_id: str,
        target_id: str,
    ) -> Tuple[bool, str, Optional[ConnectionRequest]]:
        """Initiate connection request obeying daily limits and relationship restrictions."""
        if sender_id == target_id:
            return False, "You cannot send a connection request to yourself.", None

        if await self._block_repo.is_blocked(sender_id, target_id):
            return False, "Unable to send connection request.", None

        # Check existing friendship
        f = await self._friendship_repo.get_friendship(sender_id, target_id)
        if f and f.status == FriendshipStatus.ACTIVE:
            return False, "You are already friends with this user.", None

        # Check existing pending request
        existing_req = await self._request_repo.get_pending_between(sender_id, target_id)
        if existing_req:
            return False, "A pending connection request already exists between you.", None

        # Daily request quota check
        ent = await self._subscription_service.get_or_create_entitlement(sender_id)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        usage = await self._daily_usage_repo.get_or_create(sender_id, today)

        if usage.requests_count >= ent.daily_requests_limit:
            return (
                False,
                f"Daily request quota reached ({ent.daily_requests_limit}/{ent.daily_requests_limit}). "
                "Upgrade your subscription to send more requests.",
                None,
            )

        # Increment quota count
        await self._daily_usage_repo.increment_request(sender_id, today)

        req = ConnectionRequest(
            id=f"req_{uuid.uuid4().hex[:12]}",
            sender_id=sender_id,
            target_id=target_id,
            status=ConnectionRequestStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        await self._request_repo.save(req)
        return True, "Connection request sent!", req

    async def accept_connection_request(
        self,
        request_id: str,
        user_id: str,
    ) -> Tuple[bool, str, Optional[Friendship]]:
        """Accept connection request and form atomic canonical friendship."""
        req = await self._request_repo.get_by_id(request_id)
        if not req or req.target_id != user_id or req.status != ConnectionRequestStatus.PENDING:
            return False, "Connection request not found or already resolved.", None

        # Enforce friend capacity for both participants
        sender_friends = await self._friendship_repo.count_user_friends(req.sender_id)
        if not await self._subscription_service.can_add_friend(req.sender_id, sender_friends):
            return False, "The sender has reached their maximum friend limit.", None

        target_friends = await self._friendship_repo.count_user_friends(req.target_id)
        if not await self._subscription_service.can_add_friend(req.target_id, target_friends):
            return False, "You have reached your maximum friend limit. Upgrade your subscription to add more friends.", None

        # Update request
        req.accept()
        await self._request_repo.save(req)

        # Create canonical friendship
        friendship = Friendship.create(req.sender_id, req.target_id, source="CONNECTION_REQUEST")
        await self._friendship_repo.save(friendship)

        return True, "Connection request accepted! You are now friends. 💙", friendship

    async def reject_connection_request(
        self,
        request_id: str,
        user_id: str,
    ) -> Tuple[bool, str]:
        """Decline incoming connection request."""
        req = await self._request_repo.get_by_id(request_id)
        if not req or req.target_id != user_id or req.status != ConnectionRequestStatus.PENDING:
            return False, "Connection request not found or already resolved."

        req.reject()
        await self._request_repo.save(req)
        return True, "Connection request declined."

    async def get_incoming_requests(self, user_id: str) -> List[dict]:
        """List pending incoming connection requests."""
        requests = await self._request_repo.get_incoming_requests(user_id)
        results = []

        for r in requests:
            sender = await self._user_repo.get_by_id(r.sender_id)
            display_id = sender.display_user_id if sender else r.sender_id
            results.append({
                "request_id": r.id,
                "sender_id": r.sender_id,
                "sender_display_id": display_id,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M UTC"),
            })

        return results
