"""
likby.repositories.sqlite.daily_usage_repository
aiosqlite implementation of DailyUsageRepository.
"""

import aiosqlite
from likby.domain.entities.daily_usage import DailyUsage
from likby.repositories.interfaces import DailyUsageRepository


class SqliteDailyUsageRepository(DailyUsageRepository):
    """SQLite implementation of DailyUsageRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def get_or_create(self, user_id: str, usage_date: str) -> DailyUsage:
        try:
            async with self._conn.execute(
                "SELECT user_id, usage_date, searches_count, requests_count, uploads_count, received_count FROM daily_usage WHERE user_id = ? AND usage_date = ?",
                (user_id, usage_date),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return DailyUsage(
                        user_id=row[0],
                        usage_date=row[1],
                        searches_count=row[2],
                        requests_count=row[3],
                        uploads_count=row[4] if len(row) > 4 else 0,
                        received_count=row[5] if len(row) > 5 else 0,
                    )
        except Exception:
            # Fallback for schemas with only 4 columns
            async with self._conn.execute(
                "SELECT user_id, usage_date, searches_count, requests_count FROM daily_usage WHERE user_id = ? AND usage_date = ?",
                (user_id, usage_date),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return DailyUsage(
                        user_id=row[0],
                        usage_date=row[1],
                        searches_count=row[2],
                        requests_count=row[3],
                        uploads_count=0,
                        received_count=0,
                    )

        # Create new usage record for today
        usage = DailyUsage(user_id=user_id, usage_date=usage_date)
        try:
            await self._conn.execute(
                "INSERT OR IGNORE INTO daily_usage (user_id, usage_date, searches_count, requests_count, uploads_count, received_count) VALUES (?, ?, 0, 0, 0, 0)",
                (user_id, usage_date),
            )
        except Exception:
            await self._conn.execute(
                "INSERT OR IGNORE INTO daily_usage (user_id, usage_date, searches_count, requests_count) VALUES (?, ?, 0, 0)",
                (user_id, usage_date),
            )
        await self._conn.commit()
        return usage

    async def increment_search(self, user_id: str, usage_date: str) -> int:
        await self.get_or_create(user_id, usage_date)
        await self._conn.execute(
            "UPDATE daily_usage SET searches_count = searches_count + 1 WHERE user_id = ? AND usage_date = ?",
            (user_id, usage_date),
        )
        await self._conn.commit()
        async with self._conn.execute(
            "SELECT searches_count FROM daily_usage WHERE user_id = ? AND usage_date = ?",
            (user_id, usage_date),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 1

    async def increment_request(self, user_id: str, usage_date: str) -> int:
        await self.get_or_create(user_id, usage_date)
        await self._conn.execute(
            "UPDATE daily_usage SET requests_count = requests_count + 1 WHERE user_id = ? AND usage_date = ?",
            (user_id, usage_date),
        )
        await self._conn.commit()
        async with self._conn.execute(
            "SELECT requests_count FROM daily_usage WHERE user_id = ? AND usage_date = ?",
            (user_id, usage_date),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 1

    async def increment_upload(self, user_id: str, usage_date: str) -> int:
        await self.get_or_create(user_id, usage_date)
        try:
            await self._conn.execute(
                "UPDATE daily_usage SET uploads_count = uploads_count + 1 WHERE user_id = ? AND usage_date = ?",
                (user_id, usage_date),
            )
            await self._conn.commit()
            async with self._conn.execute(
                "SELECT uploads_count FROM daily_usage WHERE user_id = ? AND usage_date = ?",
                (user_id, usage_date),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 1
        except Exception:
            return 1

    async def increment_received(self, user_id: str, usage_date: str) -> int:
        await self.get_or_create(user_id, usage_date)
        try:
            await self._conn.execute(
                "UPDATE daily_usage SET received_count = received_count + 1 WHERE user_id = ? AND usage_date = ?",
                (user_id, usage_date),
            )
            await self._conn.commit()
            async with self._conn.execute(
                "SELECT received_count FROM daily_usage WHERE user_id = ? AND usage_date = ?",
                (user_id, usage_date),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 1
        except Exception:
            return 1

