# LikBy Scalability & Failure Modes Analysis

---

## 1. Concurrency & Scalability Targets

| Metric | MVP / Development | Target Production (Year 1) | High Scale Target |
|:---|:---|:---|:---|
| **Daily Active Users (DAU)** | 100 - 1,000 | 10,000 | 50,000+ |
| **Peak Updates / Sec** | 10 updates/sec | 100 updates/sec | 500 updates/sec |
| **Active Games Concurrency** | 20 sessions | 500 sessions | 2,500 sessions |
| **Database Strategy** | SQLite WAL mode | Supabase Pooler (PgBouncer) | Read-Replicas + Redis Cache |

---

## 2. Failure Modes & Mitigations

### 2.1 Telegram Flood Control (429 Too Many Requests)
- **Cause:** Exceeding 30 messages/sec globally or 1 message/sec per recipient.
- **Mitigation:** Token-bucket rate limiter with exponential backoff and jitter (`src/likby/services/chat_relay_service.py`). Transient errors pause queue dispatch for `retry_after` seconds.

### 2.2 Cloudflare R2 Archival Timeout
- **Cause:** Network latency or intermittent S3-compatible API disruption during media upload.
- **Mitigation:** Two-phase decoupling. Telegram delivery occurs via native Telegram `file_id` immediately; archival to R2 is queued as a background task. If R2 fails after 3 retries, the item is moved to an administrative dead-letter queue without interrupting user chat.

### 2.3 Firestore Outage during Chat Session Creation
- **Cause:** Firestore API unavailability or quota exhaustion.
- **Mitigation:** Relational match state remains authoritative in PostgreSQL/SQLite. The chat session creation task is recorded in the outbox table and retried with backoff.
