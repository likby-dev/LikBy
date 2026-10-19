# LikBy Reliability & Error-Handling Architecture

**Platform:** LikBy  
**Last Updated:** 2026-10-19  

---

## 1. Core Error-Handling Principles

1. **Fail-Fast Configuration:** Application settings in `src/likby/config.py` are strictly validated at process boot using Pydantic Settings. Missing critical configuration (such as invalid `BOT_TOKEN`) halts startup immediately with actionable error messages.
2. **No Blanket Swallowing:** Exceptions are never discarded silently with empty `except:` or generic `catch (e) { return null; }`. Every boundary either maps the error to a typed response, logs structured context, or deliberately propagates.
3. **Correlation ID Everywhere:** Every incoming HTTP request is assigned or preserves an `X-Request-Id` header (via `request_correlation_and_security_middleware`). Unhandled exceptions log this ID, and error responses return it to clients without leaking tracebacks or database queries.

---

## 2. Global Exception Handling & HTTP Status Mapping

```
                                  Client Request
                                        │
                                        ▼
                  ┌───────────────────────────────────────────┐
                  │ request_correlation_and_security_middleware│
                  └─────────────────────┬─────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │                                       │
            Success Path                            Exception Raised
                    │                                       │
                    ▼                                       ▼
             Response Body                        Exception Handler
                    │                                       │
                    ▼                         ┌─────────────┴─────────────┐
        Headers Appended:                     ▼                           ▼
        • X-Request-Id                 HTTPException             Generic Exception
        • X-Content-Type-Options        (Custom Handler)           (500 Fallback)
        • X-Frame-Options                     │                           │
        • X-Response-Time-Ms                  ▼                           ▼
                                      { "detail": ...,           { "error": "InternalServerError",
                                        "status_code": ...,        "message": "...",
                                        "request_id": ... }        "request_id": ... }
```

---

## 3. Asynchronous Task Lifecycle & Graceful Teardown

### 3.1 Webhook Update Worker Task Retention
- In `src/likby/main.py`, background tasks spawned to process Telegram webhook updates are registered into an `app.state.active_update_tasks` set:
  ```python
  task = asyncio.create_task(_safe_feed_update(data))
  app.state.active_update_tasks.add(task)
  task.add_done_callback(app.state.active_update_tasks.discard)
  ```
- **Garbage Collection Safety:** Avoids Python runtime garbage-collecting in-flight tasks before completion.
- **Graceful Draining:** During container shutdown (e.g. Render redeploy), `lifespan` waits up to 5.0 seconds for in-flight tasks to finish before closing database pools and bot sessions:
  ```python
  pending_updates = getattr(app.state, "active_update_tasks", set())
  if pending_updates:
      with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
          await asyncio.wait_for(asyncio.gather(*list(pending_updates), return_exceptions=True), timeout=5.0)
  ```

### 3.2 Background Workers
- **Matchmaker Worker:** Runs on a non-blocking 2.0s tick (`matchmaker_background_worker`). Suppresses and recovers from transient ticket errors.
- **Outbox Worker:** Dispatches pending notifications on a 3.0s interval with bounded exponential backoff (`outbox_backoff_base_seconds=2.0`, max attempts = 10).
- **Maintenance Cron:** Executes hourly reap cycles (`maintenance_cron.py`), expiring stale chat tickets, 24-hour Spark passes, and orphaned invitations.

---

## 4. WebSocket Resilience & Disconnect Handling

- **Connection Protocol:** `/api/v1/play/ws/{session_id}`
- **Authentication:** Validated via token query or Telegram `initData`. Unauthenticated callers are rejected with WS 1008 Policy Violation.
- **Session Participant Validation:** The connection manager verifies that the authenticated user is an authorized participant (`get_participants`) in the specified session.
- **Heartbeat & Keep-Alive:** Supports ping/pong cycles (`{"type": "ping"}` $\to$ `{"type": "pong"}`) to maintain connection across NAT firewalls.
- **Graceful Cleanup:** `WebSocketDisconnect` cleanly removes the socket from `PlayConnectionManager.active_connections` without memory leakage or room corruption.
