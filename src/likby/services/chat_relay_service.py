"""
likby.services.chat_relay_service
Anonymous chat message relay service with durable persistence, ordering, and outbox delivery.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from aiogram import Bot
from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.message import ChatMessage
from likby.domain.entities.outbox import OutboxJob
from likby.domain.enums import (
    MessageDeliveryStatus,
    MessageType,
    OutboxJobStatus,
    TerminationReason,
)
from likby.repositories.interfaces import (
    ChatSessionRepository,
    MessageRepository,
    OutboxRepository,
    UserRepository,
)
from likby.services.media_quota_service import MediaQuotaService
from likby.services.media_storage_service import MediaService
from likby.services.session_cache import ActiveSessionCache, CachedSession


class ChatRelayService:
    """Relays text and media between paired anonymous users with durable persistence."""

    def __init__(
        self,
        bot: Bot,
        session_cache: ActiveSessionCache,
        session_repo: ChatSessionRepository,
        user_repo: UserRepository,
        message_repo: Optional[MessageRepository] = None,
        outbox_repo: Optional[OutboxRepository] = None,
        media_service: Optional[MediaService] = None,
        media_quota_service: Optional[MediaQuotaService] = None,
    ) -> None:
        self._bot = bot
        self._session_cache = session_cache
        self._session_repo = session_repo
        self._user_repo = user_repo
        self._message_repo = message_repo
        self._outbox_repo = outbox_repo
        self._media_service = media_service
        self._media_quota_service = media_quota_service

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

    async def record_system_event(self, session_id: str, text: str) -> Optional[ChatMessage]:
        """Record an auditable SYSTEM event message in the session history."""
        if not self._message_repo:
            return None

        seq = await self._message_repo.get_next_sequence(session_id)
        msg = ChatMessage(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            sender_id="SYSTEM",
            sender_display_id="SYSTEM",
            sequence=seq,
            message_type=MessageType.SYSTEM,
            text=text,
            delivery_status=MessageDeliveryStatus.DELIVERED,
        )
        await self._message_repo.save(msg)
        return msg

    async def relay_text(self, sender_tg_id: int, text: str) -> bool:
        """
        Durable relay of text message to session peer.
        Persists record, attempts delivery, and queues to outbox on transient failure.
        """
        cached = await self.get_or_warm_session(sender_tg_id)
        if not cached:
            return False

        partner_tg_id = cached.get_partner_tg_id(sender_tg_id)
        sender_user_id = (
            cached.user_a_id if sender_tg_id == cached.user_a_tg_id else cached.user_b_id
        )

        # Retrieve sender entity for stable display handle
        sender_user = await self._user_repo.get_by_id(sender_user_id)
        sender_display = sender_user.display_user_id if sender_user else sender_user_id

        # 1. Persist message record with deterministic sequence
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        if self._message_repo:
            seq = await self._message_repo.get_next_sequence(cached.session_id)
            message = ChatMessage(
                id=msg_id,
                session_id=cached.session_id,
                sender_id=sender_user_id,
                sender_display_id=sender_display,
                sequence=seq,
                message_type=MessageType.TEXT,
                text=text,
                delivery_status=MessageDeliveryStatus.PENDING,
            )
            await self._message_repo.save(message)

        # 2. Deliver to partner via Telegram
        delivery_ok = False
        try:
            tg_msg = await self._bot.send_message(
                chat_id=partner_tg_id,
                text=text,
            )
            delivery_ok = True
            if self._message_repo:
                await self._message_repo.update_delivery_status(
                    message_id=msg_id,
                    status=MessageDeliveryStatus.DELIVERED,
                    telegram_msg_id=tg_msg.message_id,
                )
        except Exception as exc:
            if self._message_repo:
                await self._message_repo.update_delivery_status(
                    message_id=msg_id,
                    status=MessageDeliveryStatus.FAILED,
                )
            if self._outbox_repo:
                job = OutboxJob(
                    id=f"job_{uuid.uuid4().hex[:12]}",
                    session_id=cached.session_id,
                    message_id=msg_id,
                    recipient_tg_id=partner_tg_id,
                    status=OutboxJobStatus.PENDING,
                    last_error=str(exc),
                )
                await self._outbox_repo.save(job)
            return False

        # 3. Update activity timestamp in database
        db_session = await self._session_repo.get_by_id(cached.session_id)
        if db_session:
            db_session.record_message()
            await self._session_repo.save(db_session)

        return delivery_ok

    async def relay_media(
        self,
        sender_tg_id: int,
        message_type: MessageType,
        file_id: str,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        file_size: Optional[int] = None,
    ) -> bool:
        """
        Durable relay of media attachments (photo, video, voice, document, sticker)
        with quota enforcement, protected delivery (protect_content=True), and storage archival.
        """
        cached = await self.get_or_warm_session(sender_tg_id)
        if not cached:
            return False

        partner_tg_id = cached.get_partner_tg_id(sender_tg_id)
        sender_user_id = (
            cached.user_a_id if sender_tg_id == cached.user_a_tg_id else cached.user_b_id
        )
        partner_user_id = (
            cached.user_b_id if sender_tg_id == cached.user_a_tg_id else cached.user_a_id
        )

        sender_user = await self._user_repo.get_by_id(sender_user_id)
        sender_display = sender_user.display_user_id if sender_user else sender_user_id

        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        asset_id: Optional[str] = None

        # Quota checks & reservation (if quota service is configured)
        upload_key = f"up_{cached.session_id}_{msg_id}_{file_id[:16]}"
        recv_key = f"rec_{cached.session_id}_{msg_id}_{partner_user_id}_{file_id[:16]}"

        if self._media_quota_service:
            limits = await self._media_quota_service.get_user_media_limits(sender_user_id)
            # File size limit check
            if file_size is not None:
                max_bytes = (
                    limits["max_video_size_bytes"]
                    if message_type == MessageType.VIDEO
                    else limits["max_image_size_bytes"]
                )
                if file_size > max_bytes:
                    max_mb = max_bytes // (1024 * 1024)
                    await self._bot.send_message(
                        chat_id=sender_tg_id,
                        text=f"💜 This file exceeds your {limits['display_name']} size limit of {max_mb} MB. Upgrade your plan with /subscribe to send larger files.",
                    )
                    return False

            # Check upload quota
            up_ok, up_used, up_limit, up_reason = await self._media_quota_service.check_upload_quota(
                user_id=sender_user_id,
                idempotency_key=upload_key,
            )
            if not up_ok:
                await self._bot.send_message(chat_id=sender_tg_id, text=up_reason)
                return False

            # Check and reserve recipient receive quota
            rec_ok, rec_reason = await self._media_quota_service.reserve_receive_quota(
                recipient_id=partner_user_id,
                media_file_id=file_id,
                idempotency_key=recv_key,
            )
            if not rec_ok:
                await self._bot.send_message(
                    chat_id=sender_tg_id,
                    text="💜 Your conversation partner has reached today's media receiving limit and cannot receive media at this time.",
                )
                return False

            # Commit sender upload quota
            await self._media_quota_service.reserve_and_commit_upload(
                user_id=sender_user_id,
                media_file_id=file_id,
                idempotency_key=upload_key,
            )

        # Archive media in background if bytes provided and media service available
        if file_bytes and self._media_service:
            safe_name = file_name or f"media_{file_id[:8]}"
            m_type = mime_type or "application/octet-stream"
            asset_uuid = f"ast_{uuid.uuid4().hex[:12]}"
            asset = await self._media_service.archive_media(
                asset_id=asset_uuid,
                session_id=cached.session_id,
                message_id=msg_id,
                data=file_bytes,
                mime_type=m_type,
                original_filename=safe_name,
                telegram_file_id=file_id,
            )
            if asset:
                asset_id = asset.id

        if self._message_repo:
            seq = await self._message_repo.get_next_sequence(cached.session_id)
            message = ChatMessage(
                id=msg_id,
                session_id=cached.session_id,
                sender_id=sender_user_id,
                sender_display_id=sender_display,
                sequence=seq,
                message_type=message_type,
                text=caption,
                media_asset_id=asset_id,
                delivery_status=MessageDeliveryStatus.PENDING,
            )
            await self._message_repo.save(message)

        # Forward via Telegram with content protection (protect_content=True)
        tg_msg_id: Optional[int] = None
        try:
            if message_type == MessageType.PHOTO:
                sent = await self._bot.send_photo(
                    chat_id=partner_tg_id,
                    photo=file_id,
                    caption=caption,
                    protect_content=True,
                )
            elif message_type == MessageType.VIDEO:
                sent = await self._bot.send_video(
                    chat_id=partner_tg_id,
                    video=file_id,
                    caption=caption,
                    protect_content=True,
                )
            elif message_type == MessageType.VOICE:
                sent = await self._bot.send_voice(
                    chat_id=partner_tg_id,
                    voice=file_id,
                    caption=caption,
                    protect_content=True,
                )
            elif message_type == MessageType.DOCUMENT:
                sent = await self._bot.send_document(
                    chat_id=partner_tg_id,
                    document=file_id,
                    caption=caption,
                    protect_content=True,
                )
            elif message_type == MessageType.STICKER:
                sent = await self._bot.send_sticker(
                    chat_id=partner_tg_id,
                    sticker=file_id,
                    protect_content=True,
                )
            else:
                sent = await self._bot.send_message(
                    chat_id=partner_tg_id,
                    text=f"[{message_type.value}] {caption or ''}",
                    protect_content=True,
                )
            tg_msg_id = sent.message_id

            if self._message_repo:
                await self._message_repo.update_delivery_status(
                    message_id=msg_id,
                    status=MessageDeliveryStatus.DELIVERED,
                    telegram_msg_id=tg_msg_id,
                )

            # Successfully delivered -> commit recipient receive quota
            if self._media_quota_service:
                await self._media_quota_service.commit_receive_quota(
                    recipient_id=partner_user_id,
                    idempotency_key=recv_key,
                )
        except Exception:
            if self._message_repo:
                await self._message_repo.update_delivery_status(
                    message_id=msg_id,
                    status=MessageDeliveryStatus.FAILED,
                )
            # Failed delivery -> rollback recipient receive quota (recipient is never charged for failed delivery)
            if self._media_quota_service:
                await self._media_quota_service.rollback_receive_quota(
                    recipient_id=partner_user_id,
                    idempotency_key=recv_key,
                )
            return False

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
        """Terminate the active session, record system event, notify partner, and evict cache."""
        cached = await self.get_or_warm_session(sender_tg_id)
        if not cached:
            return None

        sender_user_id = (
            cached.user_a_id if sender_tg_id == cached.user_a_tg_id else cached.user_b_id
        )
        partner_tg_id = cached.get_partner_tg_id(sender_tg_id)

        # 1. Record system event in transcript
        await self.record_system_event(
            session_id=cached.session_id,
            text=f"Session ended ({reason.value}).",
        )

        # 2. Update session status in DB
        db_session = await self._session_repo.get_by_id(cached.session_id)
        if db_session:
            db_session.end(ended_by=sender_user_id, reason=reason)
            await self._session_repo.save(db_session)

        # 3. Evict from in-memory cache
        await self._session_cache.remove(cached.session_id)

        # 4. Notify partner with post-session prompt (Ratings / Likes)
        try:
            await self._bot.send_message(
                chat_id=partner_tg_id,
                text=(
                    "🛑 <b>Your conversation partner has left the chat.</b>\n\n"
                    "How was your conversation? You can rate your partner or find a new match."
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass  # Partner might have blocked bot

        return db_session
