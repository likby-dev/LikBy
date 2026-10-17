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

    # Database Configuration
    database_backend: Literal["sqlite", "postgres", "firestore"] = "sqlite"
    database_url: str = "sqlite+aiosqlite:///likby.db"
    database_direct_url: Optional[str] = None
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    # Storage Configuration
    storage_provider: Literal["local", "r2"] = "local"
    media_store_dir: str = "media_store"

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
        v = v.strip().rstrip("/")
        if "://" in v:
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("BASE_URL must be a valid HTTP or HTTPS URL.")
        else:
            v = f"https://{v}"
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
