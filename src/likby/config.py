"""
likby.config
Typed configuration management using Pydantic Settings.
"""

from functools import lru_cache
from typing import Literal, Optional
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production application settings with strict validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core Environment
    environment: Literal["development", "testing", "staging", "production"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    timezone: str = "Asia/Kolkata"

    # Server Networking
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = Field(default="http://localhost:8000", description="Base public URL")

    # Telegram Platform Credentials
    bot_token: SecretStr = Field(..., description="Telegram Bot API token from @BotFather")
    webhook_secret_token: SecretStr = Field(
        default=SecretStr("default_secret_token_at_least_32_characters_long_1234"),
        description="Secret token for Telegram webhook verification",
    )
    bot_mode: Literal["webhook", "polling"] = "polling"
    telegram_mini_app_url: Optional[str] = Field(
        default=None,
        description="Configured Telegram Mini App WebApp URL for LikBy Play",
    )
    telegram_max_download_bytes: int = 20971520  # 20 MB

    # Relational Database Configuration (Supabase PostgreSQL / Cloud)
    database_backend: Literal["sqlite", "postgres", "supabase", "firestore"] = "postgres"
    database_url: str = ""
    database_direct_url: Optional[str] = None
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    supabase_publishable_key: Optional[str] = None
    supabase_secret_key: Optional[SecretStr] = None
    supabase_db_url: Optional[str] = None
    supabase_db_sslmode: str = "require"
    supabase_db_pool_min: int = 1
    supabase_db_pool_max: int = 5

    # Firebase Cloud Firestore Configuration (Conversations & Transcripts)
    firebase_project_id: Optional[str] = None
    firestore_database_id: str = "(default)"
    google_application_credentials: Optional[str] = None
    firestore_emulator_host: Optional[str] = None

    # Binary Media Storage (Supabase Storage / Cloudflare R2)
    storage_provider: Literal["local", "r2", "supabase"] = "supabase"
    media_store_dir: str = "media_store"
    r2_account_id: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[SecretStr] = None
    r2_bucket_name: str = "likby-media"
    r2_endpoint_url: Optional[str] = None
    r2_region: str = "auto"
    r2_presigned_url_ttl_seconds: int = 300
    r2_max_upload_bytes: int = 20971520  # 20 MB

    # Durable Outbox & Cross-Service Worker Configuration
    outbox_batch_size: int = 25
    outbox_poll_interval_seconds: float = 2.0
    outbox_max_attempts: int = 10
    outbox_backoff_base_seconds: float = 2.0
    outbox_backoff_max_seconds: float = 300.0
    request_timeout_seconds: float = 20.0
    shutdown_grace_seconds: float = 20.0

    # Social & Entitlements Configuration
    default_friend_limit: int = 3
    default_daily_search_limit: int = 3
    default_daily_request_limit: int = 5

    # Security & Retention Configuration
    transcript_retention_days: int = 365
    media_retention_days: int = 365
    rate_limit_enabled: bool = True

    # Firestore & Transcript Configuration
    firestore_write_max_attempts: int = 5
    firestore_retry_base_seconds: float = 1.0
    firestore_retry_max_seconds: float = 30.0
    transcript_default_page_size: int = 100
    transcript_max_page_size: int = 500

    # Payment Provider Configuration
    payment_mode: Literal["test", "live"] = "test"
    razorpay_key_id: Optional[str] = None
    razorpay_key_secret: Optional[SecretStr] = None
    razorpay_webhook_secret: Optional[SecretStr] = None

    # AI Feature Flags & Keys (Optional)
    ai_enabled: bool = False
    ai_provider: Literal["groq", "gemini", "mock"] = "mock"
    ai_api_key: Optional[SecretStr] = None

    # Rate Limiting & Safety
    rate_limit_webhook_rps: int = 30
    user_message_rate_limit: int = 5  # Max messages per 5 seconds

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v: SecretStr) -> SecretStr:
        token_str = v.get_secret_value()
        parts = token_str.split(":")
        if len(parts) != 2 or not parts[0].isdigit():
            raise ValueError(
                "Invalid Telegram bot token format. Must be '<bot_id>:<token_hash>'."
            )
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        import os
        render_url = os.environ.get("RENDER_EXTERNAL_URL")
        render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        actual_base = render_url or (f"https://{render_host}" if render_host else None)

        if actual_base and ("localhost" in v or "127.0.0.1" in v or "likby-app.onrender.com" in v):
            return actual_base.strip().rstrip("/")

        v = v.strip().rstrip("/")
        if "likby-app.onrender.com" in v:
            if actual_base:
                return actual_base.strip().rstrip("/")
            v = v.replace("likby-app.onrender.com", "likby.onrender.com")

        if "://" in v:
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("BASE_URL must be a valid HTTP or HTTPS URL.")
        else:
            v = f"https://{v}"
        return v

    @field_validator("telegram_mini_app_url")
    @classmethod
    def validate_telegram_mini_app_url(cls, v: Optional[str]) -> Optional[str]:
        import os
        render_url = os.environ.get("RENDER_EXTERNAL_URL")
        render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        actual_base = render_url or (f"https://{render_host}" if render_host else None)

        if not v:
            if actual_base:
                return f"{actual_base.strip().rstrip('/')}/play"
            return v

        v = v.strip().rstrip("/")
        # Fix legacy or incorrect service name 'likby-app.onrender.com'
        if "likby-app.onrender.com" in v:
            if actual_base:
                return f"{actual_base.strip().rstrip('/')}/play"
            v = v.replace("likby-app.onrender.com", "likby.onrender.com")

        if actual_base and "onrender.com" in v and "localhost" not in actual_base:
            return f"{actual_base.strip().rstrip('/')}/play"

        return v

    @property
    def effective_mini_app_url(self) -> str:
        """Returns the canonical public Mini App URL guaranteed to have a trailing slash."""
        url = self.telegram_mini_app_url or f"{self.base_url.rstrip('/')}/play/"
        if "likby-app.onrender.com" in url:
            url = url.replace("likby-app.onrender.com", "likby.onrender.com")
        if not url.endswith("/"):
            url += "/"
        return url


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
