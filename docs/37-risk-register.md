# 37 — Risk Register

## Purpose

Identify, evaluate, and mitigate architectural, security, privacy, operational, and platform risks across the Tikible project lifecycle.

## Scope

Covers technical infrastructure, third-party platform dependencies, privacy governance, user safety, and financial constraints.

---

## Risk Assessment Matrix (Heatmap)

```
        Impact  |  Low   |  Medium  |   High   | Critical
Likelihood      |        |          |          |
----------------+--------+----------+----------+---------
High            |        | RSK-003  | RSK-001  | 
Medium          | RSK-008| RSK-006  | RSK-002  | RSK-004
Low             | RSK-010| RSK-007  | RSK-005  | RSK-009
```

---

## Detailed Risk Inventory

| Risk ID | Category | Description | Likelihood | Impact | Severity | Mitigation Strategy | Contingency Plan |
|---|---|---|---|---|---|---|---|
| **RSK-001** | Platform | Telegram Bot Account suspended or restricted due to user spam reports | High | High | **CRITICAL** | Strict age gate, automated rate limiting, prominent in-chat `/report` feature to handle abuse internally rather than via Telegram client reports. | Maintain alternative standby bot token; accelerate standalone Web / Mini App client rollout. |
| **RSK-002** | Infrastructure | Render Free Tier erases local SQLite database upon container restart | High | Med | **HIGH** | Explicitly document SQLite as ephemeral dev-only tier; prioritize Supabase PostgreSQL connection before user onboarding. | Run automated `backup_sqlite.py` script syncing snapshots to S3/R2 every 6 hours. |
| **RSK-003** | Platform | Outbound rate limit exceeded (Telegram 30 msgs/sec global limit) | High | Med | **HIGH** | In-memory token bucket rate limiter; batch status updates; use `editMessageReplyMarkup` instead of `sendMessage` for game moves. | Buffer non-urgent messages in Redis queue with exponential backoff on HTTP 429. |
| **RSK-004** | Privacy | Chat message bodies inadvertently leaked into application logs or database | Med | Critical | **CRITICAL** | Architectural zero-persistence rule: relay service passes text strictly in memory; structlog processor redacts all sensitive fields; automated privacy tests in CI. | Emergency log purge; revoke database credentials; deploy immediate hotfix. |
| **RSK-005** | Safety | Coordinated infiltration by spammers, commercial bots, or bad actors | Med | High | **HIGH** | Behavioral velocity checks; new user onboarding captcha gate; karma penalty for fast skips; auto-quarantine upon 3 user reports. | Activate emergency kill switch `MATCHMAKING_ENABLED=false` to halt new pairings. |
| **RSK-006** | Performance | SQLite `database is locked` errors during concurrent read/write transactions | Med | Med | **MEDIUM** | Configure WAL mode (`PRAGMA journal_mode=WAL`), set 5-second `busy_timeout`, keep write transactions sub-millisecond. | Migrate repository layer to Supabase PostgreSQL with connection pooler. |
| **RSK-007** | Security | Webhook spoofing by malicious third-party posting forged updates | Low | High | **MEDIUM** | Enforce `X-Telegram-Bot-Api-Secret-Token` header validation at the FastAPI middleware ingress layer before parsing payloads. | Drop connection immediately with HTTP 403; ban originating IP. |
| **RSK-008** | Operational | Inactivity sleep (cold start) causing 45-second delay for users | High | Low | **MEDIUM** | Deploy external uptime monitor (BetterStack / UptimeRobot) pinging `/health/live` every 10 minutes to keep container warm. | Upgrade Render plan to Starter ($7/month). |
| **RSK-009** | Legal / Safety | Underage users bypassing self-declaration age verification gate | Med | Critical | **CRITICAL** | Explicit mandatory age consent dialog; strict terms of service; immediate ban upon any report of underage presence. | Consult legal counsel; maintain audit log of consent timestamps. |
| **RSK-010** | Technical | AI Provider (Groq/Gemini) outage causing icebreaker failures | Med | Low | **LOW** | Provider abstraction wraps calls in circuit breaker with 2-second timeout; transparently falls back to curated static prompt library. | Disable AI generation flag `AI_ENABLED=false` without service restart. |

---

## Risk Monitoring & Review Cadence

- **Weekly Review**: Review report volumes, false positive bans, and database storage growth.
- **Pre-Release Review**: Verify all high-severity mitigations remain intact before merging to `main`.
- **Incident Retrospective**: Any unexpected outage or security event triggers an immediate risk register update.
