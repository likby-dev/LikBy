"""
tikible.services.chat_relay_service
Anonymous chat message relay service enforcing zero-persistence privacy.
"""

from typing import Optional
from aiogram import Bot
from tikible.domain.entities.chat_session import ChatSession
from tikible.domain.enums import TerminationReason
from tikible.repositories.interfaces import ChatSessionRepository, UserRepository
from tikible.services.session_cache import ActiveSessionCache, CachedSession


class ChatRelayService:
    """Relays text messages between paired anonymous users in real-time."""

    def __init__(
        self,
        bot: Bot,
        session_cache: ActiveSessionCache,
        session_repo: ChatSessionRepository,
        user_repo: UserRepository,
    ) -> None:
        self._bot = bot
        self._session_cache = session_cache
        self._session_repo = session_repo
        self._user_repo = user_repo

    async def get_or_warm_session(self, tg_id: int) -> Optional[CachedSession]:
        """Retrieve active cached session or warm from database."""
        cached = await self._session_cache.get_by_telegram_id(tg_id)
        if cached:
            return cached

        user = await self._user_repo.get_by_telegram_id(tg_id)
        if not user:
            return None

        db_session = await self._session_repo.get_active_by_user_id(user.id)
        if not db_session:
            return None

        user_a = await self._user_repo.get_by_id(db_session.user_a_id)
        user_b = await self._user_repo.get_by_id(db_session.user_b_id)
        if not user_a or not user_b:
            return None

        cached = CachedSession(
            session_id=db_session.id,
            user_a_id=user_a.id,
            user_b_id=user_b.id,
            user_a_tg_id=user_a.telegram_id,
            user_b_tg_id=user_b.telegram_id,
        )
        await self._session_cache.put(cached)
        return cached

    async def relay_text(self, sender_tg_id: int, text: str) -> bool:
        """
        Relay user text message to anonymous partner.
        PRIVACY GUARANTEE: `text` is never saved to disk, database, or telemetry.
        """
        cached = await self.get_or_warm_session(sender_tg_id)
        if not cached:
            return False

        partner_tg_id = cached.get_partner_tg_id(sender_tg_id)

        # Forward message via Telegram Bot API
        await self._bot.send_message(
            chat_id=partner_tg_id,
            text=text,
        )

        # Update activity timestamp in database asynchronously
        db_session = await self._session_repo.get_by_id(cached.session_id)
        if db_session:
            db_session.record_message()
            await self._session_repo.save(db_session)

        return True

    async def end_active_session(
        self,
        sender_tg_id: int,
        reason: TerminationReason = TerminationReason.USER_STOPPED,
    ) -> Optional[ChatSession]:
        """Terminate the active session, notify partner, and evict cache."""
        cached = await self.get_or_warm_session(sender_tg_id)
        if not cached:
            return None

        sender_user_id = (
            cached.user_a_id if sender_tg_id == cached.user_a_tg_id else cached.user_b_id
        )
        partner_tg_id = cached.get_partner_tg_id(sender_tg_id)

        db_session = await self._session_repo.get_by_id(cached.session_id)
        if db_session:
            db_session.end(ended_by=sender_user_id, reason=reason)
            await self._session_repo.save(db_session)

        # Evict from in-memory cache
        await self._session_cache.remove(cached.session_id)

        # Notify partner
        try:
            await self._bot.send_message(
                chat_id=partner_tg_id,
                text=(
                    "🛑 <b>Your conversation partner has left the chat.</b>\n\n"
                    "Tap <b>🎲 Find a Match</b> to start a new anonymous conversation."
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass  # Partner might have blocked bot

        return db_session
