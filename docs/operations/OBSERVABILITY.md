# LikBy Observability, Metrics & Structured Logging

---

## 1. Logging Architecture
- **Format:** Structured JSON output via Python `logging`.
- **Fields:** `timestamp`, `level`, `correlation_id`, `event_type`, `user_id_hash`, `handler`, `duration_ms`.
- **Privacy Sanitization:** User tokens, message text, and payment credentials are automatically redacted before logging.
