"""
likby.repositories.postgres.database
PostgreSQL / Supabase connection pool management using asyncpg.
"""

from typing import Optional
import asyncpg
from likby.config import Settings


class PostgresDatabase:
    """Manages asyncpg connection pool to Supabase PostgreSQL."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> asyncpg.Pool:
        """Initialize asyncpg connection pool."""
        if self._pool is not None:
            return self._pool

        db_url = self._settings.supabase_db_url or self._settings.database_url
        if not db_url or "sqlite" in db_url:
            raise ValueError("PostgresDatabase requires a valid PostgreSQL / Supabase connection string.")

        # Clean URL if necessary (strip postgresql+asyncpg:// if provided)
        clean_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

        self._pool = await asyncpg.create_pool(
            dsn=clean_url,
            min_size=self._settings.supabase_db_pool_min,
            max_size=self._settings.supabase_db_pool_max,
            ssl=self._settings.supabase_db_sslmode if self._settings.supabase_db_sslmode != "disable" else None,
        )
        return self._pool

    async def close(self) -> None:
        """Close connection pool gracefully."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("PostgresDatabase pool is not connected. Call connect() first.")
        return self._pool
