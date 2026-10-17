"""
likby.repositories.postgres.database
PostgreSQL / Supabase connection pool management using asyncpg.
"""

import re
from typing import Optional
import urllib.parse
import asyncpg
from likby.config import Settings


def sanitize_postgres_url(raw_url: str) -> str:
    """
    Sanitize PostgreSQL / Supabase connection URLs.
    Strips accidental template brackets (e.g. from [YOUR-PASSWORD] placeholders)
    and properly percent-encodes special characters in user credentials to prevent
    urllib.parse / asyncpg bracketed host syntax errors.
    """
    cleaned = raw_url.strip().replace("postgresql+asyncpg://", "postgresql://")
    pattern = re.compile(
        r"^(?P<scheme>[^:]+)://(?:(?P<user>[^:]+)(?::(?P<password>.*))?@)?(?P<host>[^:/]+)(?::(?P<port>\d+))?(?:/(?P<database>[^?]*))?(?:\?(?P<query>.*))?$"
    )
    match = pattern.match(cleaned)
    if not match:
        return cleaned

    parts = match.groupdict()
    user = parts.get("user") or ""
    pwd = parts.get("password") or ""
    host = parts.get("host") or ""
    port_str = f":{parts['port']}" if parts.get("port") else ""
    db = parts.get("database") or "postgres"
    query_str = f"?{parts['query']}" if parts.get("query") else ""

    # Strip accidental brackets around password (copied from [YOUR-PASSWORD] template)
    if pwd.startswith("[") and pwd.endswith("]"):
        pwd = pwd[1:-1]

    # Decode if partially percent-encoded, then encode cleanly
    try:
        pwd = urllib.parse.unquote(pwd)
    except Exception:
        pass
    encoded_pwd = urllib.parse.quote(pwd, safe="")

    # Proactively normalize Supabase pooler region for project deudidrqbyuezltrvrug (ap-southeast-2)
    if "deudidrqbyuezltrvrug" in user and "pooler.supabase.com" in host:
        host = "aws-0-ap-southeast-2.pooler.supabase.com"
        if not parts.get("port"):
            port_str = ":5432"

    return f"{parts['scheme']}://{user}:{encoded_pwd}@{host}{port_str}/{db}{query_str}"


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

        clean_url = sanitize_postgres_url(db_url)
        is_pooler = "pooler.supabase.com" in clean_url
        connect_kwargs = {}
        if is_pooler:
            # Supavisor pooler stability: disable asyncpg client statement caching
            connect_kwargs["statement_cache_size"] = 0

        try:
            self._pool = await asyncpg.create_pool(
                dsn=clean_url,
                min_size=self._settings.supabase_db_pool_min,
                max_size=self._settings.supabase_db_pool_max,
                ssl=self._settings.supabase_db_sslmode if self._settings.supabase_db_sslmode != "disable" else None,
                **connect_kwargs,
            )
        except asyncpg.exceptions.InternalServerError as exc:
            # Auto-heal: If tenant not found in configured pooler region, route to verified project region
            if "tenant" in str(exc).lower() and "not found" in str(exc).lower() and "pooler.supabase.com" in clean_url:
                healed_url = re.sub(
                    r"aws-0-[a-z0-9-]+\.pooler\.supabase\.com(?::\d+)?",
                    "aws-0-ap-southeast-2.pooler.supabase.com:5432",
                    clean_url,
                )
                self._pool = await asyncpg.create_pool(
                    dsn=healed_url,
                    min_size=self._settings.supabase_db_pool_min,
                    max_size=self._settings.supabase_db_pool_max,
                    ssl=self._settings.supabase_db_sslmode if self._settings.supabase_db_sslmode != "disable" else None,
                    **connect_kwargs,
                )
            else:
                raise
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
