# 39 — Architecture Decision Records (ADRs)

## Purpose

Maintain a formal historical record of critical architectural decisions, context, evaluated alternatives, and consequences for Tikible.

---

## ADR Index

| ADR ID | Decision Title | Status | Date |
|---|---|---|---|
| [ADR-001](#adr-001-telegram-bot-as-initial-launch-platform) | Telegram Bot as Initial Launch Platform | **DECIDED** | 2026-10-15 |
| [ADR-002](#adr-002-technology-stack-python-311-aiogram-3x-fastapi) | Technology Stack: Python 3.11+, aiogram 3.x, FastAPI | **DECIDED** | 2026-10-15 |
| [ADR-003](#adr-003-storage-tier-sqlite-wal-mode-for-mvp) | Storage Tier: SQLite WAL Mode for MVP | **DECIDED** | 2026-10-15 |
| [ADR-004](#adr-004-target-production-storage-supabase-postgresql) | Target Production Storage: Supabase PostgreSQL | **DECIDED** | 2026-10-15 |
| [ADR-005](#adr-005-zero-persistence-architecture-for-chat-messages) | Zero-Persistence Architecture for Chat Messages | **DECIDED** | 2026-10-15 |
| [ADR-006](#adr-006-server-authoritative-multiplayer-game-engine) | Server-Authoritative Multiplayer Game Engine | **DECIDED** | 2026-10-15 |
| [ADR-007](#adr-007-telegram-html-parse-mode-over-markdownv2) | Telegram HTML Parse Mode over MarkdownV2 | **DECIDED** | 2026-10-15 |
| [ADR-008](#adr-008-in-memory-session-cache-for-relay-routing) | In-Memory Session Cache for Relay Routing | **DECIDED** | 2026-10-15 |
| [ADR-009](#adr-009-webhook-ingress-with-immediate-http-200-ack) | Webhook Ingress with Immediate HTTP 200 Ack | **DECIDED** | 2026-10-15 |
| [ADR-010](#adr-010-ai-provider-abstraction-with-static-fallback) | AI Provider Abstraction with Static Fallback | **DECIDED** | 2026-10-15 |
| [ADR-011](#adr-011-strict-type-checking-with-mypy-and-pydantic-v2) | Strict Type Checking with Mypy and Pydantic v2 | **DECIDED** | 2026-10-15 |
| [ADR-012](#adr-012-inactivity-reaper-lifecycle-4m-warning-5m-close) | Inactivity Reaper Lifecycle: 4m Warning, 5m Close | **DECIDED** | 2026-10-15 |

---

### ADR-001: Telegram Bot as Initial Launch Platform

- **Status**: DECIDED
- **Context**: Tikible requires rapid user validation without the friction of app store downloads, native mobile installations, or custom push notification infrastructure.
- **Decision**: Launch the MVP as a Telegram bot.
- **Consequences**:
  - *Positive*: Zero installation friction for Telegram's 900M+ users; built-in notifications; cross-platform compatibility.
  - *Negative*: Subject to Telegram platform policies, rate limits (30 msg/s), and UI rendering constraints.

---

### ADR-002: Technology Stack: Python 3.11+, aiogram 3.x, FastAPI

- **Status**: DECIDED
- **Context**: Need a modern, asynchronous backend capable of high I/O concurrency, strict typing, clean architecture separation, and seamless Telegram API integration.
- **Decision**: Adopt Python 3.11+, `aiogram 3.x` for the Telegram adapter, and `FastAPI` / `Uvicorn` for HTTP webhook ingress.
- **Consequences**:
  - *Positive*: Native `asyncio` event loop performance; typed domain models with Pydantic; decoupling of bot logic from web routes.
  - *Negative*: Requires careful event loop hygiene to avoid blocking operations.

---

### ADR-003: Storage Tier: SQLite WAL Mode for MVP

- **Status**: DECIDED
- **Context**: The MVP requires zero-cost, zero-setup local development and automated CI testing without external cloud account dependencies.
- **Decision**: Use SQLite with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and `aiosqlite` for MVP development.
- **Consequences**:
  - *Positive*: Instant zero-config setup; full relational transactions; simple in-memory testing.
  - *Negative*: Single-writer serialization; ephemeral on Render free tier (requires backup runbook or cloud DB for persistence).

---

### ADR-004: Target Production Storage: Supabase PostgreSQL

- **Status**: DECIDED
- **Context**: Production requires persistent remote storage, multi-writer concurrency, connection pooling, and automated backups.
- **Decision**: Select Supabase (managed PostgreSQL) as the target production database, accessed via repository interfaces.
- **Consequences**:
  - *Positive*: High concurrency; GIN indexing for interests; automated backups; connection pooling via Supavisor.
  - *Negative*: Requires managing connection limits on pooled vs direct ports.

---

### ADR-005: Zero-Persistence Architecture for Chat Messages

- **Status**: DECIDED
- **Context**: User privacy and legal compliance require that anonymous conversations cannot be leaked, subpoenaed, or compromised in data breaches.
- **Decision**: Chat messages are forwarded purely in volatile memory. No message text is ever written to the database or logged to disk.
- **Consequences**:
  - *Positive*: Maximum privacy guarantee; zero database storage cost for chat logs; immune to message data breaches.
  - *Negative*: Messages cannot be retrieved after delivery; abuse moderation relies on user reports and optional ephemeral client-submitted snippets.

---

### ADR-006: Server-Authoritative Multiplayer Game Engine

- **Status**: DECIDED
- **Context**: Multiplayer games (Tic-Tac-Toe) must be tamper-proof, resilient to network drops, and prevent turn-stealing.
- **Decision**: The backend acts as the sole authoritative source of game state. Every move is validated against the server-side state machine.
- **Consequences**:
  - *Positive*: Impossible to cheat or make illegal moves; reliable draw/win detection.
  - *Negative*: Adds small round-trip latency for move validation.

---

### ADR-007: Telegram HTML Parse Mode over MarkdownV2

- **Status**: DECIDED
- **Context**: MarkdownV2 in Telegram requires escaping 18 special characters (`.`, `!`, `-`, `(`, etc.), causing frequent parsing crashes when formatting dynamic text.
- **Decision**: Standardize all Telegram message formatting on HTML (`parse_mode=ParseMode.HTML`).
- **Consequences**:
  - *Positive*: Robust escaping with standard `html.escape()`; eliminates parse failure exceptions.
  - *Negative*: Slightly more verbose template strings than raw markdown.

---

### ADR-008: In-Memory Session Cache for Relay Routing

- **Status**: DECIDED
- **Context**: Querying the database to resolve partner Telegram IDs for every incoming message adds 20-50ms latency.
- **Decision**: Maintain an in-memory concurrent map (`ActiveSessionCache`) indexed by user ID and Telegram ID.
- **Consequences**:
  - *Positive*: Sub-millisecond lookup; reduces database read load by over 90%.
  - *Negative*: In-memory cache is local to the worker instance (requires Redis if scaled horizontally).

---

### ADR-009: Webhook Ingress with Immediate HTTP 200 Ack

- **Status**: DECIDED
- **Context**: If Telegram webhook updates are not acknowledged within 5 seconds, Telegram re-sends the update, causing message duplicate storms.
- **Decision**: The FastAPI webhook handler immediately returns HTTP 200 OK after basic validation, scheduling message processing in an async background task.
- **Consequences**:
  - *Positive*: Prevents duplicate message loops and Telegram retry timeouts.
  - *Negative*: Processing errors must be handled asynchronously without surfacing directly in the HTTP response.

---

### ADR-010: AI Provider Abstraction with Static Fallback

- **Status**: DECIDED
- **Context**: AI-generated icebreakers must not become a single point of failure or cause runaway API costs.
- **Decision**: Create an `AIProvider` interface with a circuit breaker that falls back to a curated static prompt catalog on timeout, rate limit, or failure.
- **Consequences**:
  - *Positive*: 100% uptime for icebreaker delivery; zero cost when offline.
  - *Negative*: Fallback prompts lack dynamic customization.

---

### ADR-011: Strict Type Checking with Mypy and Pydantic v2

- **Status**: DECIDED
- **Context**: Prevent runtime type errors, missing attribute bugs, and unvalidated environment inputs in production.
- **Decision**: Enforce `mypy --strict` and `pydantic >= 2.7` across all codebase modules.
- **Consequences**:
  - *Positive*: Catches type bugs at CI time; self-documenting data models.
  - *Negative*: Slightly more initial boilerplate for type annotations.

---

### ADR-012: Inactivity Reaper Lifecycle: 4m Warning, 5m Close

- **Status**: DECIDED
- **Context**: Abandoned chats keep users locked in active sessions and consume memory.
- **Decision**: Run a background monitor every 30 seconds. If a chat is silent for 4 minutes, post a warning; at 5 minutes, close the session automatically.
- **Consequences**:
  - *Positive*: Frees up abandoned sessions; prompts users to continue chatting.
  - *Negative*: Occasional premature closure for slow-typing users.
