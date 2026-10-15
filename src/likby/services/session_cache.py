"""
likby.services.session_cache
Sub-millisecond in-memory cache mapping active chat participants.
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class CachedSession:
    """In-memory active session descriptor."""
    session_id: str
    user_a_id: str
    user_b_id: str
    user_a_tg_id: int
    user_b_tg_id: int

    def get_partner_tg_id(self, sender_tg_id: int) -> int:
        if sender_tg_id == self.user_a_tg_id:
            return self.user_b_tg_id
        elif sender_tg_id == self.user_b_tg_id:
            return self.user_a_tg_id
        raise ValueError(f"Telegram ID {sender_tg_id} not in session {self.session_id}")

    def get_partner_user_id(self, sender_user_id: str) -> str:
        if sender_user_id == self.user_a_id:
            return self.user_b_id
        elif sender_user_id == self.user_b_id:
            return self.user_a_id
        raise ValueError(f"User ID {sender_user_id} not in session {self.session_id}")


class ActiveSessionCache:
    """Thread-safe in-memory cache for active chat sessions."""

    def __init__(self) -> None:
        self._by_user_id: Dict[str, CachedSession] = {}
        self._by_tg_id: Dict[int, CachedSession] = {}
        self._lock = asyncio.Lock()

    async def put(self, session: CachedSession) -> None:
        async with self._lock:
            self._by_user_id[session.user_a_id] = session
            self._by_user_id[session.user_b_id] = session
            self._by_tg_id[session.user_a_tg_id] = session
            self._by_tg_id[session.user_b_tg_id] = session

    async def get_by_telegram_id(self, tg_id: int) -> Optional[CachedSession]:
        return self._by_tg_id.get(tg_id)

    async def get_by_user_id(self, user_id: str) -> Optional[CachedSession]:
        return self._by_user_id.get(user_id)

    async def remove(self, session_id: str) -> None:
        async with self._lock:
            tg_keys = [k for k, v in self._by_tg_id.items() if v.session_id == session_id]
            for k in tg_keys:
                self._by_tg_id.pop(k, None)

            user_keys = [k for k, v in self._by_user_id.items() if v.session_id == session_id]
            for k in user_keys:
                self._by_user_id.pop(k, None)
