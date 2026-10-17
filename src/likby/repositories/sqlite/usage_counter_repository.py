"""
likby.repositories.sqlite.usage_counter_repository
aiosqlite implementation of UsageCounterRepository.
"""

from typing import Dict
import aiosqlite
from likby.domain.enums import FeatureKey
from likby.repositories.interfaces import UsageCounterRepository


class SqliteUsageCounterRepository(UsageCounterRepository):
    """SQLite atomic quota consumption and rate-limiting repository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def get_usage(self, user_id: str, feature_key: FeatureKey, period_start: str) -> int:
        async with self._conn.execute(
            "SELECT used FROM usage_counters WHERE user_id = ? AND feature_key = ? AND period_start = ?",
            (user_id, feature_key.value, period_start),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def increment_usage(
        self,
        user_id: str,
        feature_key: FeatureKey,
        period_start: str,
        period_end: str,
        delta: int = 1,
    ) -> int:
        counter_id = f"use_{user_id}_{feature_key.value}_{period_start}"
        await self._conn.execute(
            """
            INSERT INTO usage_counters (id, user_id, feature_key, period_start, period_end, used, version)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(user_id, feature_key, period_start) DO UPDATE SET
                used = used + excluded.used,
                version = version + 1
            """,
            (counter_id, user_id, feature_key.value, period_start, period_end, delta),
        )
        await self._conn.commit()
        return await self.get_usage(user_id, feature_key, period_start)

    async def get_user_daily_summary(self, user_id: str, date_str: str) -> Dict[str, int]:
        summary = {k.value: 0 for k in FeatureKey}
        async with self._conn.execute(
            "SELECT feature_key, used FROM usage_counters WHERE user_id = ? AND period_start = ?",
            (user_id, date_str),
        ) as cursor:
            async for row in cursor:
                summary[row[0]] = row[1]
        return summary
