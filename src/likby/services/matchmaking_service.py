"""
likby.services.matchmaking_service
Matchmaking service handling queue registration, cancellation, and compatibility pairing.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid
from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.match_ticket import MatchTicket
from likby.domain.entities.profile import Profile
from likby.domain.matching.scorer import calculate_match_score
from likby.repositories.interfaces import (
    BlockRepository,
    ChatSessionRepository,
    MatchTicketRepository,
    UserRepository,
)
from likby.services.session_cache import ActiveSessionCache, CachedSession


class MatchmakingService:
    """Orchestrates matchmaking queue and pairwise matching execution."""

    def __init__(
        self,
        ticket_repo: MatchTicketRepository,
        session_repo: ChatSessionRepository,
        block_repo: BlockRepository,
        user_repo: UserRepository,
        session_cache: ActiveSessionCache,
    ) -> None:
        self._ticket_repo = ticket_repo
        self._session_repo = session_repo
        self._block_repo = block_repo
        self._user_repo = user_repo
        self._session_cache = session_cache

    async def enqueue(self, user_id: str, profile: Profile) -> MatchTicket:
        """Create and persist a new matchmaking search ticket."""
        ticket = MatchTicket(
            id=f"tkt_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            user_gender=profile.gender,
            user_age=profile.age,
            languages=profile.languages,
            interests=profile.interests,
            preferred_genders=profile.preferred_gender_filter,
            min_age=profile.min_age_filter,
            max_age=profile.max_age_filter,
        )
        await self._ticket_repo.save(ticket)
        return ticket

    async def cancel(self, user_id: str) -> bool:
        """Cancel any active waiting ticket for a user."""
        ticket = await self._ticket_repo.get_active_by_user_id(user_id)
        if not ticket:
            return False
        ticket.cancel()
        await self._ticket_repo.save(ticket)
        return True

    async def run_matchmaker_cycle(self) -> List[Tuple[MatchTicket, MatchTicket, ChatSession]]:
        """
        Evaluate waiting queue and create chat sessions for compatible pairs.
        Returns list of newly formed (ticket_a, ticket_b, session).
        """
        waiting_tickets = await self._ticket_repo.get_waiting_tickets(limit=100)
        matched_pairs: List[Tuple[MatchTicket, MatchTicket, ChatSession]] = []
        already_matched_ids = set()

        for i, tkt_a in enumerate(waiting_tickets):
            if tkt_a.id in already_matched_ids:
                continue

            for tkt_b in waiting_tickets[i + 1 :]:
                if tkt_b.id in already_matched_ids:
                    continue
                if tkt_a.user_id == tkt_b.user_id:
                    continue

                # Check reciprocal block barrier
                if await self._block_repo.is_blocked(tkt_a.user_id, tkt_b.user_id):
                    continue

                # Calculate score
                score, common_ints, common_langs = calculate_match_score(
                    user_a_gender=tkt_a.user_gender,
                    user_a_pref=tkt_a.preferred_genders,
                    user_a_age=tkt_a.user_age,
                    user_a_age_range=(tkt_a.min_age, tkt_a.max_age),
                    user_a_languages=tkt_a.languages,
                    user_a_interests=tkt_a.interests,
                    user_b_gender=tkt_b.user_gender,
                    user_b_pref=tkt_b.preferred_genders,
                    user_b_age=tkt_b.user_age,
                    user_b_age_range=(tkt_b.min_age, tkt_b.max_age),
                    user_b_languages=tkt_b.languages,
                    user_b_interests=tkt_b.interests,
                )

                if score >= 0.5:
                    session_id = f"ses_{uuid.uuid4().hex[:12]}"
                    tkt_a.mark_matched(partner_user_id=tkt_b.user_id, session_id=session_id)
                    tkt_b.mark_matched(partner_user_id=tkt_a.user_id, session_id=session_id)

                    session = ChatSession(
                        id=session_id,
                        user_a_id=tkt_a.user_id,
                        user_b_id=tkt_b.user_id,
                        match_score=score,
                        match_metadata={
                            "common_interests": list(common_ints),
                            "common_languages": list(common_langs),
                        },
                    )

                    # Persist updates
                    await self._ticket_repo.save(tkt_a)
                    await self._ticket_repo.save(tkt_b)
                    await self._session_repo.save(session)

                    # Update in-memory session cache
                    user_a = await self._user_repo.get_by_id(tkt_a.user_id)
                    user_b = await self._user_repo.get_by_id(tkt_b.user_id)
                    if user_a and user_b:
                        await self._session_cache.put(
                            CachedSession(
                                session_id=session_id,
                                user_a_id=user_a.id,
                                user_b_id=user_b.id,
                                user_a_tg_id=user_a.telegram_id,
                                user_b_tg_id=user_b.telegram_id,
                            )
                        )

                    already_matched_ids.add(tkt_a.id)
                    already_matched_ids.add(tkt_b.id)
                    matched_pairs.append((tkt_a, tkt_b, session))
                    break

        return matched_pairs
