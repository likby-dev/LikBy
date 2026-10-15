# 27 — Observability & Operations

## Purpose

Define logging standards, metrics collection, distributed tracing, health check protocols, and operational alerting thresholds for LikBy.

## Scope

Covers runtime diagnostics, structured JSON logging, privacy-safe sanitization, Prometheus metrics export, and operational dashboards.

---

## Observability Architecture

```mermaid
graph LR
    subgraph LikBy Core
        App[FastAPI / aiogram]
        Logger[Structlog Logger]
        Metrics[Prometheus Registry]
    end

    subgraph Observability Sinks
        Stdout[Standard Output<br/>JSON Format]
        PromEndpoint[/metrics<br/>Scraped Endpoint]
    end

    subgraph External Platforms
        RenderLogs[Render Log Stream]
        BetterStack[BetterStack / Datadog]
        PrometheusServer[Prometheus / Grafana]
    end

    App --> Logger
    App --> Metrics
    Logger --> Stdout
    Metrics --> PromEndpoint
    Stdout --> RenderLogs
    RenderLogs --> BetterStack
    PromEndpoint --> PrometheusServer
```

---

## Structured Logging & Privacy Redaction

Logs are emitted to `stdout` in machine-parseable JSON format using `structlog`.

### Privacy Logging Rule (CRITICAL)
- **NEVER** log chat message text or sensitive user inputs.
- **NEVER** log Telegram auth bot tokens or webhook secret tokens.
- **HASH** or truncate Telegram user IDs in debug logs if required by privacy policy.

```python
# src/likby/observability/logging.py
import logging
import structlog
from typing import Any, Dict

def sanitize_sensitive_data(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Filter out message text, tokens, and personally identifiable info."""
    for sensitive_key in ("text", "message_content", "bot_token", "token", "password", "evidence_snippet"):
        if sensitive_key in event_dict:
            event_dict[sensitive_key] = "[REDACTED]"
    return event_dict

def setup_logging(log_level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            sanitize_sensitive_data,
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

### Log Schema Standard

Every log event contains contextual metadata:
```json
{
  "timestamp": "2026-10-15T14:40:22.102Z",
  "level": "info",
  "event": "chat_session_created",
  "update_id": 9823412,
  "session_id": "ses_5e6f7g8h",
  "user_a_id": "usr_9f8e7d6c",
  "user_b_id": "usr_1a2b3c4d",
  "match_score": 0.82,
  "duration_ms": 34.2
}
```

---

## Health Check Protocols

LikBy provides standard RFC-compliant health endpoints in `likby/api/routes/health.py`:

### 1. Liveness Probe (`GET /health/live`)
Returns HTTP 200 as long as the Uvicorn worker process is alive.
```json
{
  "status": "ok",
  "uptime_seconds": 3600
}
```

### 2. Readiness Probe (`GET /health/ready`)
Verifies critical downstream dependencies before accepting traffic:
- Database connectivity (executes `SELECT 1`)
- Telegram Bot API reachability (executes lightweight `get_me` cache check)

```python
# Route handler
@router.get("/health/ready")
async def readiness_check(
    db: DatabaseConnection = Depends(get_db),
    bot: Bot = Depends(get_bot)
) -> JSONResponse:
    checks = {}
    is_healthy = True

    # 1. DB Check
    try:
        await db.execute("SELECT 1")
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
        is_healthy = False

    # 2. Telegram Bot Token Check
    try:
        await bot.get_me()
        checks["telegram_api"] = "healthy"
    except Exception as e:
        checks["telegram_api"] = f"unhealthy: {str(e)}"
        is_healthy = False

    status_code = 200 if is_healthy else 503
    return JSONResponse(status_code=status_code, content={"status": "ready" if is_healthy else "degraded", "checks": checks})
```

---

## Prometheus Key Metrics

LikBy exposes Prometheus metrics at `GET /metrics` protected by an internal bearer token:

| Metric Name | Type | Description |
|---|---|---|
| `likby_http_requests_total` | Counter | Total incoming webhook requests labeled by `status_code` |
| `likby_http_request_duration_seconds` | Histogram | Latency distribution of webhook handling |
| `likby_active_chat_sessions` | Gauge | Number of active two-way chat sessions |
| `likby_matchmaking_queue_size` | Gauge | Number of tickets waiting in matchmaking queue |
| `likby_messages_relayed_total` | Counter | Cumulative count of relayed text messages |
| `likby_games_active` | Gauge | Currently active Tic-Tac-Toe matches |
| `likby_reports_submitted_total` | Counter | Cumulative user moderation reports filed |

---

## Alerting Thresholds & Operational Runbook

| Condition | Severity | Trigger Threshold | Recommended Action |
|---|---|---|---|
| **High Webhook Errors** | `CRITICAL` | 5xx responses > 2% over 5m | Check database locks; verify Telegram bot token validity. |
| **Relay Delivery Lag** | `WARNING` | p95 relay latency > 1,500ms | Scale workers; inspect Telegram Bot API rate limits (HTTP 429). |
| **Queue Starvation** | `WARNING` | Tickets waiting > 10m without match | Inspect matchmaking filter bounds and queue tick worker loop. |
| **Abuse Report Spike** | `WARNING` | > 10 reports in 10m | Check for spam bot coordinated attack; activate strict captcha / gate. |
| **Memory Pressure** | `CRITICAL` | RAM usage > 450 MB (88% of 512MB) | Trigger memory dump; identify active cache leaks; restart instance. |
