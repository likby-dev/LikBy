# 28 — Render Deployment

## Purpose

Define the production deployment configuration, infrastructure-as-code blueprints, runtime environment, and operational procedures for deploying Tikible on Render.

## Scope

Covers `render.yaml`, web service configuration, persistent disk constraints, startup lifecycle, and webhook synchronization.

---

## Infrastructure Blueprint (`render.yaml`)

Render supports Infrastructure as Code via `render.yaml` committed to the repository root:

```yaml
services:
  - type: web
    name: tikible-app
    env: python
    region: oregon # or frankfurt depending on target audience
    plan: free # Upgrade to 'starter' ($7/mo) for persistent uptime
    buildCommand: "pip install --upgrade pip && pip install -e '.[prod]'"
    startCommand: "uvicorn tikible.main:app --host 0.0.0.0 --port $PORT --workers 1"
    healthCheckPath: /health/ready
    autoDeploy: true
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.9
      - key: ENVIRONMENT
        value: production
      - key: LOG_LEVEL
        value: INFO
      - key: BOT_TOKEN
        sync: false # Set securely in Render dashboard
      - key: WEBHOOK_SECRET_TOKEN
        generateValue: true # Render generates a secure random 32-char token
      - key: BASE_URL
        fromService:
          type: web
          name: tikible-app
          property: host
      - key: DATABASE_BACKEND
        value: sqlite # Change to 'postgres' once Supabase is connected
      - key: DATABASE_URL
        value: sqlite+aiosqlite:////data/tikible.db
```

---

## The Storage & Persistence Reality on Render

> [!CAUTION]
> **Render Free Tier Ephemeral File System**
> On the free tier, Render does NOT offer persistent disks. Any local file created in the container filesystem (including `/data/tikible.db`) is **completely erased** when:
> 1. The container spins down after 15 minutes of inactivity.
> 2. A new code deployment occurs.
> 3. The container is restarted for maintenance.

### Architecture Adaptation Strategy

To run with persistent user data, two supported options exist:

```mermaid
graph TD
    subgraph Option A: Render Paid Disk
        RAppA[Tikible Web Service<br/>Render Starter Plan $7/mo]
        RDisk[(Render Persistent Disk<br/>1 GB @ $0.25/mo)]
        RAppA -->|aiosqlite| RDisk
    end

    subgraph Option B: Managed Cloud Postgres (Recommended)
        RAppB[Tikible Web Service<br/>Render Free or Starter]
        SupaDB[(Supabase Managed Postgres<br/>Free Tier 500MB)]
        RAppB -->|asyncpg pool| SupaDB
    end
```

1. **Option A (Persistent SQLite)**: Upgrade Render service to `starter` ($7/mo) and attach a 1 GB persistent disk ($0.25/mo) mounted at `/data`.
2. **Option B (Remote PostgreSQL — Recommended)**: Keep Render web service and point `DATABASE_URL` to a remote Supabase or Neon PostgreSQL database.

---

## Application Startup & Webhook Registration Lifecycle

When Tikible boots on Render, the FastAPI lifespan event orchestrates startup checks and registers the webhook with Telegram:

```python
# src/tikible/main.py lifespan implementation
from contextlib import asynccontextmanager
from fastapi import FastAPI
from aiogram import Bot
from tikible.config import get_settings
from tikible.repositories.factory import init_database

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    
    # 1. Initialize Database Schema
    db = await init_database(settings)
    app.state.db = db

    # 2. Register Webhook with Telegram
    bot = Bot(token=settings.bot_token)
    webhook_url = f"{settings.base_url}/api/v1/telegram/webhook"
    
    await bot.set_webhook(
        url=webhook_url,
        secret_token=settings.webhook_secret_token,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=False # Prevent dropping messages during deploys
    )
    app.state.bot = bot

    yield # Running application

    # 3. Graceful Teardown
    await bot.session.close()
    await db.close()
```

---

## Render Deployment Verification Checklist

After deploying to Render:

1. **Check Build Logs**: Verify `pip install -e '.[prod]'` succeeds without compilation errors.
2. **Check Container Status**: Ensure status transitions from `Building` -> `Deploying` -> `Live`.
3. **Verify Webhook Status via Telegram Bot API**:
   ```bash
   curl -s "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo" | jq .
   ```
   *Expected Output:*
   ```json
   {
     "ok": true,
     "result": {
       "url": "https://tikible-app.onrender.com/api/v1/telegram/webhook",
       "has_custom_certificate": false,
       "pending_update_count": 0,
       "last_error_date": null,
       "last_error_message": null
     }
   }
   ```
4. **Trigger Health Endpoint**:
   ```bash
   curl -i https://tikible-app.onrender.com/health/ready
   # Expected: HTTP/1.1 200 OK
   ```

---

## Troubleshooting Common Render Issues

### 1. `502 Bad Gateway` on Startup
- **Root Cause**: FastAPI did not bind to `0.0.0.0` or did not use `$PORT` provided by Render.
- **Fix**: Verify start command includes `--host 0.0.0.0 --port $PORT`.

### 2. Inactivity Cold Starts (45-60s Delay)
- **Root Cause**: On the free tier, Render sleeps inactive apps after 15 minutes.
- **Fix**: Configure an external uptime ping (e.g., UptimeRobot, BetterStack) to hit `/health/live` every 10 minutes, or upgrade to Render Starter plan.

### 3. Out-Of-Memory (OOM) Termination (Exit Code 137)
- **Root Cause**: Memory consumption exceeded 512 MB.
- **Fix**: Ensure Uvicorn runs with `--workers 1`. Multiple workers in 512MB will trigger OOM.
