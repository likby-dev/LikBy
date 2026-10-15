# 00 — Executive Summary

## Purpose

This document provides the high-level overview of Tikible: what it is, who it serves, and the foundational technical decisions that shape the entire system.

## Product

Tikible is a **privacy-first anonymous social matching and real-time chat platform**. Users are paired with compatible strangers for anonymous one-to-one text conversations. The initial client is a **Telegram bot**; a web application and Telegram Mini App will share the same backend in the future.

### Core Principles

1. **Privacy by default** — No conversation history stored. Telegram IDs never exposed to other users. Minimum data collection.
2. **Anonymous conversations** — Matched participants communicate through a relay. Neither party knows the other's identity unless both consent to reveal.
3. **Free core experience** — Basic matching and chatting never paywalled.
4. **Safety controls everywhere** — Block, report, and disconnect at any time.
5. **Fair matching** — Deterministic, explainable algorithm. AI enhances but never replaces safety rules.
6. **Low operating costs** — SQLite locally, free-tier deployment, optional AI.
7. **Modular architecture** — Grows from Telegram bot to multi-client platform without rewriting business logic.

### Target Audience

Adults aged 18+ seeking anonymous social conversations. The platform is **not** a dating app, though compatible-interest matching may surface romantic connections. It is **not** a content platform, forum, or group chat system.

## Key Architecture Decisions

| # | Decision | Status | Rationale |
|---|---|---|---|
| ADR-001 | Python + FastAPI + aiogram 3.x | DECIDED | Async-native, strong typing, rapid development, good Telegram support |
| ADR-002 | FastAPI owns all business logic | DECIDED | Single source of truth; Telegram bot is an adapter, not a business logic container |
| ADR-003 | SQLite for initial storage | DECIDED | Zero-cost, zero-dependency local development; repository interfaces enable future migration |
| ADR-004 | Repository pattern with interface contracts | DECIDED | Swap storage backends without changing domain or service code |
| ADR-005 | Webhook mode for production, long polling for dev | DECIDED | Webhooks fit Render's HTTP model; polling simplifies local development |
| ADR-006 | No conversation history persistence | DECIDED | Privacy-by-default; messages relayed in memory, never written to storage |
| ADR-007 | Deterministic matching before AI | DECIDED | Testable, predictable, works offline. AI is an optional enhancement layer |
| ADR-008 | One turn-based game for MVP | DECIDED | Proves game architecture without scope explosion. Tic-tac-toe selected |
| ADR-009 | Render free tier with documented limitations | DECIDED | Lowest cost. Ephemeral filesystem acknowledged; production requires external DB |
| ADR-010 | AI providers are optional and configurable | DECIDED | Core functionality must work without any AI API key |

## Scope

### In Scope (MVP — Telegram Bot)

- User onboarding with age eligibility check
- Profile creation and editing
- Matching preferences
- Anonymous random and interest-based matching
- Anonymous text message relay
- Session commands: `/next`, `/stop`, `/profile`, `/settings`, `/help`
- Block and report
- Rate limiting and anti-spam
- Conversation icebreakers (deterministic)
- One multiplayer turn-based game (tic-tac-toe)
- Health checks and diagnostics
- Account and data deletion
- Structured logging with redaction
- Local SQLite storage
- Render deployment configuration

### Out of Scope (Future)

- Web application frontend
- Telegram Mini App
- Supabase/Firestore storage adapters
- Premium/paid features
- Real-time graphical games
- AI-powered matching
- Multi-language interface
- Push notifications beyond Telegram
- Identity verification

## Documents

All architecture documentation is in the `docs/` directory. See [docs/README.md](README.md) for reading order.

## Related Documents

- [Product Requirements](01-product-requirements.md)
- [Scope & Roadmap](02-scope-and-roadmap.md)
- [High-Level Architecture](05-high-level-architecture.md)
- [Architecture Decisions](39-architecture-decisions.md)
- [Risk Register](37-risk-register.md)
