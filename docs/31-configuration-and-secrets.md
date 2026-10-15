# 31 — Configuration & Secrets

## Purpose

Define the typed configuration management architecture, comprehensive environment variable inventory, secret handling standards, and rotation procedures for LikBy.

## Scope

Covers runtime settings, validation rules, local development `.env` management, and cloud secret injection across development, staging, and production environments.

---

## Configuration Architecture (`pydantic-settings`)

LikBy enforces strict, fail-fast configuration parsing at application boot using `pydantic-settings`. If any required secret is missing or malformed, the process terminates immediately with an explicit error.

```python
# src/likby/config.py
from typing import Literal, Optional
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Production application settings with strict validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Core Environment
    environment: Literal["development", "testing", "staging", "production"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Server Networking
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = Field(..., description="Public HTTPS URL of the service for webhook callbacks")

    # Telegram Platform Credentials
    bot_token: SecretStr = Field(..., description="Telegram Bot API token from @BotFather")
    webhook_secret_token: SecretStr = Field(..., description="Secret token verified on Telegram webhook headers")
    bot_mode: Literal["webhook", "polling"] = "webhook"

    # Database Configuration
    database_backend: Literal["sqlite", "postgres", "firestore"] = "sqlite"
    database_url: str = "sqlite+aiosqlite:////data/likby.db"
    database_direct_url: Optional[str] = None
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    # AI Feature Flags & Keys (Optional)
    ai_enabled: bool = False
    ai_provider: Literal["groq", "gemini", "mock"] = "mock"
    ai_api_key: Optional[SecretStr] = None

    # Rate Limiting & Safety
    rate_limit_webhook_rps: int = 30
    user_message_rate_limit: int = 5 # max messages per 5 seconds

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v: SecretStr) -> SecretStr:
        token_str = v.get_secret_value()
        parts = token_str.split(":")
        if len(parts) != 2 or not parts[0].isdigit():
            raise ValueError("Invalid Telegram bot token format. Must be '<bot_id>:<hash>'")
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v.startswith("https://") and not v.startswith("http://localhost"):
            raise ValueError("BASE_URL must be HTTPS in production environments")
        return v.rstrip("/")
```

---

## Environment Variable Inventory

| Variable Name | Type | Required | Default | Sensitivity | Description |
|---|---|---|---|---|---|
| `ENVIRONMENT` | String | No | `development` | Public | Environment tier (`development`, `staging`, `production`) |
| `LOG_LEVEL` | String | No | `INFO` | Public | Log output filtering level |
| `BASE_URL` | URL | **Yes** | — | Internal | Public HTTPS address reachable by Telegram servers |
| `BOT_TOKEN` | String | **Yes** | — | **CRITICAL** | Telegram Bot API token issued by @BotFather |
| `WEBHOOK_SECRET_TOKEN` | String | **Yes** | — | **CRITICAL** | Random 32+ character hex string for update authentication |
| `BOT_MODE` | String | No | `webhook` | Public | Bot runtime mode (`webhook` or `polling` for dev) |
| `DATABASE_BACKEND` | String | No | `sqlite` | Internal | Persistence engine (`sqlite`, `postgres`, `firestore`) |
| `DATABASE_URL` | DSN | **Yes** | `sqlite+aiosqlite://...` | **CRITICAL** | Primary async database connection string |
| `DATABASE_DIRECT_URL` | DSN | No | — | **CRITICAL** | Direct Postgres connection string for migrations |
| `AI_ENABLED` | Boolean | No | `false` | Public | Enables icebreaker and AI assistant generation |
| `AI_PROVIDER` | String | No | `mock` | Public | AI backend selector (`groq`, `gemini`, `mock`) |
| `AI_API_KEY` | String | If AI active | — | **CRITICAL** | API token for selected AI provider |

---

## Secret Management Rules

1. **Never Commit Secrets**: `.env`, `.env.local`, and credential JSON files are permanently included in `.gitignore`.
2. **Pydantic `SecretStr` Enforced**: All credentials use `SecretStr` to prevent accidental logging or terminal leakage during tracebacks (masked automatically as `**********`).
3. **Template Provided**: An sanitized `.env.example` file is tracked in the repository with placeholder values and descriptive comments.

---

## Secret Rotation Runbook

### 1. Telegram Bot Token Rotation
If a bot token is compromised:
1. Open `@BotFather` on Telegram.
2. Select `/revoke` for the target bot. Copy the new token.
3. Update `BOT_TOKEN` in Render dashboard environment settings.
4. Redeploy service. The lifespan handler will automatically re-register the webhook using the new credentials.

### 2. Webhook Secret Token Rotation
1. Generate a new cryptographic token:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Update `WEBHOOK_SECRET_TOKEN` in Render dashboard.
3. Deploy. Webhook registration updates the secret token with Telegram instantly.
