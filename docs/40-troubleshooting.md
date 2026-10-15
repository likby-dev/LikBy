# 40 — Troubleshooting Runbook

## Purpose

Provide immediate diagnostic procedures, error code explanations, SQL inspection queries, and remediation runbooks for common development, deployment, and runtime failures in Tikible.

## Scope

Covers local development, Telegram Bot API edge cases, SQLite/PostgreSQL persistence errors, Render deployment issues, and user session deadlocks.

---

## Quick Diagnostic Cheatsheet

```bash
# 1. Check application readiness
curl -i https://<your-host>/health/ready

# 2. Check live Telegram webhook configuration
curl -s "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo" | jq .

# 3. Check Telegram bot identity
curl -s "https://api.telegram.org/bot<BOT_TOKEN>/getMe" | jq .

# 4. Clear pending updates and delete webhook (for local polling)
curl -s "https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook?drop_pending_updates=true" | jq .
```

---

## Local Development Issues

### 1. `TelegramConflictError: Conflict: can't use getUpdates method while webhook is active`

- **Symptom**: When running `python -m tikible.main --mode polling`, the application crashes with a conflict error.
- **Root Cause**: A webhook was previously registered for this bot token (e.g. from Render or local ngrok). Telegram does not permit long polling while a webhook is registered.
- **Solution**: Delete the active webhook before starting polling mode:
  ```bash
  curl -s "https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook"
  ```
  Or launch with the automated clear flag in dev:
  ```bash
  python -m tikible.main --mode polling --drop-webhook
  ```

---

### 2. `sqlite3.OperationalError: database is locked`

- **Symptom**: Integration tests or concurrent requests fail with an SQLite lock error.
- **Root Cause**: Another connection is holding a write transaction longer than the configured `busy_timeout`.
- **Solution**:
  1. Verify WAL mode is enabled:
     ```bash
     sqlite3 /data/tikible.db "PRAGMA journal_mode;"
     # Must return: wal
     ```
  2. Increase busy timeout to 5000ms:
     ```python
     await db.execute("PRAGMA busy_timeout = 5000;")
     ```
  3. Ensure code uses `async with db.transaction():` blocks that encapsulate only necessary write queries, not network calls.

---

### 3. `mypy` Reports Untyped Decorator on aiogram Handlers

- **Symptom**: `mypy --strict` fails with `Untyped decorator makes function "handle_start" untyped`.
- **Root Cause**: aiogram router decorators require explicit generic signatures.
- **Solution**: Ensure your router handler defines full argument types:
  ```python
  from aiogram.types import Message
  from aiogram.fsm.context import FSMContext

  @router.message(Command("start"))
  async def handle_start(message: Message, state: FSMContext) -> None:
      ...
  ```

---

## Render & Deployment Issues

### 1. Render Deploy Fails with `502 Bad Gateway`

- **Symptom**: Container starts on Render but status shows unhealthy or returns 502.
- **Root Cause**: Uvicorn is binding to `127.0.0.1` instead of `0.0.0.0`, or is ignoring `$PORT`.
- **Solution**: Update the `startCommand` in `render.yaml`:
  ```bash
  uvicorn tikible.main:app --host 0.0.0.0 --port $PORT --workers 1
  ```

---

### 2. Telegram Webhook Error: `Wrong secret token`

- **Symptom**: Telegram logs in `getWebhookInfo` report HTTP 403, and users get no response.
- **Root Cause**: The `X-Telegram-Bot-Api-Secret-Token` header sent by Telegram does not match the local `WEBHOOK_SECRET_TOKEN` environment variable.
- **Solution**: Re-register the webhook with the exact secret token:
  ```python
  await bot.set_webhook(
      url=f"{settings.base_url}/api/v1/telegram/webhook",
      secret_token=settings.webhook_secret_token.get_secret_value()
  )
  ```

---

### 3. Container Spins Down (45-Second Cold Start Delay)

- **Symptom**: Users complain the bot takes almost a minute to respond to their first message.
- **Root Cause**: Render free instances spin down after 15 minutes of zero inbound HTTP requests.
- **Solution**: 
  - Set up an external ping every 10 minutes (via UptimeRobot or cron-job.org) targeting `https://<app>.onrender.com/health/live`.
  - Upgrade Render plan to Starter ($7/month) for persistent uptime.

---

## Runtime & User Session Issues

### 1. Users Stuck in Active Chat After `/stop`

- **Symptom**: A user executed `/stop`, but their partner's messages are still arriving or neither can start a new match.
- **Diagnostic Query**:
  ```sql
  SELECT id, user_a_id, user_b_id, status, created_at, last_activity_at 
  FROM chat_sessions 
  WHERE status = 'ACTIVE' AND (user_a_id = '<USER_ID>' OR user_b_id = '<USER_ID>');
  ```
- **Remediation**:
  1. Manually terminate stale session:
     ```sql
     UPDATE chat_sessions 
     SET status = 'ENDED', ended_at = CURRENT_TIMESTAMP, termination_reason = 'MANUAL_ADMIN_OVERRIDE'
     WHERE id = '<SESSION_ID>';
     ```
  2. Clear in-memory session cache:
     ```bash
     curl -X POST https://<host>/api/v1/admin/cache/evict-session -H "Authorization: Bearer <ADMIN_KEY>" -d '{"session_id": "<SESSION_ID>"}'
     ```

---

### 2. Tic-Tac-Toe Inline Keyboard Button Shows "Query is too old"

- **Symptom**: Clicking a cell in the Tic-Tac-Toe grid displays a Telegram toast: `Error: query is too old or invalid`.
- **Root Cause**: Telegram callback queries expire if not acknowledged with `callback_query.answer()` within 10 seconds.
- **Solution**: Ensure the callback handler calls `await callback_query.answer()` immediately before processing heavy state updates:
  ```python
  @router.callback_query(TicTacToeCallback.filter())
  async def handle_game_move(callback: CallbackQuery, callback_data: TicTacToeCallback) -> None:
      # Acknowledge immediately to dismiss Telegram client spinner
      await callback.answer()
      
      # Now process move logic
      await game_service.process_move(callback_data)
  ```

---

### 3. Compatible Users Waiting in Queue Never Pair

- **Symptom**: User A and User B have overlapping interests and preferences, but both remain in queue indefinitely.
- **Diagnostic Steps**:
  1. Inspect active match tickets:
     ```sql
     SELECT id, user_id, status, criteria, created_at FROM match_tickets WHERE status = 'WAITING';
     ```
  2. Check for reciprocal blocklist barriers:
     ```sql
     SELECT * FROM user_blocks 
     WHERE (blocker_id = '<USER_A>' AND blocked_id = '<USER_B>')
        OR (blocker_id = '<USER_B>' AND blocked_id = '<USER_A>');
     ```
  3. Verify matchmaker background task is ticking:
     Check logs for `"event": "matchmaker_tick"`. If missing, verify the background worker was scheduled in the FastAPI lifespan startup.
