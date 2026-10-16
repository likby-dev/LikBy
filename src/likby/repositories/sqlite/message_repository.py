"""
likby.repositories.sqlite.message_repository
aiosqlite implementation of MessageRepository.
"""

from datetime import datetime
from typing import List, Optional
import aiosqlite
from likby.domain.entities.message import ChatMessage
from likby.domain.enums import MessageDeliveryStatus, MessageType
from likby.repositories.interfaces import MessageRepository


class SqliteMessageRepository(MessageRepository):
    """SQLite implementation of MessageRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, message: ChatMessage) -> None:
        await self._conn.execute(
            """
            INSERT INTO messages (
                id, session_id, sender_id, sender_display_id, sequence,
                message_type, text, media_asset_id, reply_to_message_id,
                telegram_message_id, delivery_status, created_at, delivered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                delivery_status = excluded.delivery_status,
                telegram_message_id = COALESCE(excluded.telegram_message_id, messages.telegram_message_id),
                delivered_at = COALESCE(excluded.delivered_at, messages.delivered_at)
            """,
            (
                message.id,
                message.session_id,
                message.sender_id,
                message.sender_display_id,
                message.sequence,
                message.message_type.value,
                message.text,
                message.media_asset_id,
                message.reply_to_message_id,
                message.telegram_message_id,
                message.delivery_status.value,
                message.created_at.isoformat(),
                message.delivered_at.isoformat() if message.delivered_at else None,
            ),
        )
        await self._conn.commit()

    async def get_by_id(self, message_id: str) -> Optional[ChatMessage]:
        async with self._conn.execute(
            """
            SELECT id, session_id, sender_id, sender_display_id, sequence,
                   message_type, text, media_asset_id, reply_to_message_id,
                   telegram_message_id, delivery_status, created_at, delivered_at
            FROM messages WHERE id = ?
            """,
            (message_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_session_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> List[ChatMessage]:
        async with self._conn.execute(
            """
            SELECT id, session_id, sender_id, sender_display_id, sequence,
                   message_type, text, media_asset_id, reply_to_message_id,
                   telegram_message_id, delivery_status, created_at, delivered_at
            FROM messages
            WHERE session_id = ?
            ORDER BY sequence ASC
            LIMIT ? OFFSET ?
            """,
            (session_id, limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_entity(r) for r in rows]

    async def get_next_sequence(self, session_id: str) -> int:
        async with self._conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM messages WHERE session_id = ?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 1

    async def update_delivery_status(
        self,
        message_id: str,
        status: MessageDeliveryStatus,
        telegram_msg_id: Optional[int] = None,
    ) -> None:
        delivered_at_str = datetime.now().isoformat() if status == MessageDeliveryStatus.DELIVERED else None
        await self._conn.execute(
            """
            UPDATE messages
            SET delivery_status = ?,
                telegram_message_id = COALESCE(?, telegram_message_id),
                delivered_at = COALESCE(?, delivered_at)
            WHERE id = ?
            """,
            (status.value, telegram_msg_id, delivered_at_str, message_id),
        )
        await self._conn.commit()

    def _row_to_entity(self, row: tuple) -> ChatMessage:
        return ChatMessage(
            id=row[0],
            session_id=row[1],
            sender_id=row[2],
            sender_display_id=row[3],
            sequence=row[4],
            message_type=MessageType(row[5]),
            text=row[6],
            media_asset_id=row[7],
            reply_to_message_id=row[8],
            telegram_message_id=row[9],
            delivery_status=MessageDeliveryStatus(row[10]),
            created_at=datetime.fromisoformat(row[11]),
            delivered_at=datetime.fromisoformat(row[12]) if row[12] else None,
        )
