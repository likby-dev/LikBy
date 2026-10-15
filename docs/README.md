# Tikible Documentation Master Catalog

This directory contains the complete, implementation-ready architecture and production engineering documentation for **Tikible** — a privacy-first anonymous social matching and real-time chat platform starting as a Telegram bot.

---

## Recommended Reading Order

1. **[00 — Executive Summary](00-executive-summary.md)**: High-level vision, problem space, core mechanics, and architecture summary.
2. **[01 — Product Requirements](01-product-requirements.md)**: Core features, user personas, MVP scope, and functional specs.
3. **[05 — High-Level Architecture](05-high-level-architecture.md)**: Clean architecture, layered boundaries, and component interaction.
4. **[14 — Matching Engine](14-matching-engine.md)**: Deterministic scoring, queue fairness, and compatibility models.
5. **[18 — Security Threat Model](18-security-threat-model.md)**: STRIDE analysis, attack surfaces, and defensive controls.
6. **[19 — Privacy & Data Governance](19-privacy-and-data-governance.md)**: Zero-persistence chat guarantee, retention, and deletion flows.
7. **[20 — Storage & Persistence](20-storage-and-persistence.md)**: MVP SQLite WAL mode and repository interface design.
8. **[28 — Render Deployment](28-render-deployment.md)** & **[29 — Free-Tier & Cost Model](29-free-tier-and-cost-model.md)**: Deployment manifests, quotas, and cost curves.
9. **[35 — Implementation Roadmap](35-implementation-roadmap.md)** & **[36 — Acceptance Criteria](36-acceptance-criteria.md)**: Step-by-step engineering execution plan.

---

## Complete Documentation Index (00 – 40)

| # | Document | Status | Description |
|---|---|---|---|
| 00 | [Executive Summary](00-executive-summary.md) | ✅ Complete | Platform vision, core mechanics, and architectural synthesis |
| 01 | [Product Requirements](01-product-requirements.md) | ✅ Complete | PRD, user stories, personas, and MVP boundaries |
| 02 | [Scope & Roadmap](02-scope-and-roadmap.md) | ✅ Complete | Phased scope matrix (MVP vs Post-MVP vs Non-Goals) |
| 03 | [Research & Assumptions](03-research-and-assumptions.md) | ✅ Complete | Technical research, API limits, and empirical benchmarks |
| 04 | [System Context](04-system-context.md) | ✅ Complete | C4 context diagram and external interface boundaries |
| 05 | [High-Level Architecture](05-high-level-architecture.md) | ✅ Complete | Clean Architecture layers and subsystem interactions |
| 06 | [Module Boundaries](06-module-boundaries.md) | ✅ Complete | Package structure, imports, and interface contracts |
| 07 | [Domain Model](07-domain-model.md) | ✅ Complete | Domain entities, value objects, and business invariant rules |
| 08 | [Entity Relationships](08-entity-relationships.md) | ✅ Complete | ER diagrams, relationship matrix, and referential integrity |
| 09 | [Data Flow](09-data-flow.md) | ✅ Complete | Sequence diagrams for onboarding, matching, relay, and abuse |
| 10 | [State Machines](10-state-machines.md) | ✅ Complete | Finite state machines for users, tickets, chats, and games |
| 11 | [Telegram Bot Design](11-telegram-bot-design.md) | ✅ Complete | Bot taxonomy, conversational flows, and keyboard layouts |
| 12 | [API Contracts](12-api-contracts.md) | ✅ Complete | Internal webhook contracts and future REST API definitions |
| 13 | [Authentication & Authorization](13-authentication-and-authorization.md) | ✅ Complete | Webhook verification, session tokens, and access control |
| 14 | [Matching Engine](14-matching-engine.md) | ✅ Complete | Deterministic scoring algorithm, ticket queues, and fairness |
| 15 | [Chat Session Lifecycle](15-chat-session-lifecycle.md) | ✅ Complete | Ephemeral relay, partner disconnects, and inactivity reaper |
| 16 | [Multiplayer Games](16-multiplayer-games.md) | ✅ Complete | Server-authoritative Tic-Tac-Toe via inline keyboards |
| 17 | [AI & ML Strategy](17-ai-and-ml-strategy.md) | ✅ Complete | Provider abstraction, icebreakers, and fallback rules |
| 18 | [Security Threat Model](18-security-threat-model.md) | ✅ Complete | STRIDE threat model, mitigation controls, and tests |
| 19 | [Privacy & Data Governance](19-privacy-and-data-governance.md) | ✅ Complete | Zero-persistence chat policy, data retention, and GDPR rights |
| 20 | [Storage & Persistence](20-storage-and-persistence.md) | ✅ Complete | SQLite WAL persistence, schema, and repository interfaces |
| 21 | [Supabase Architecture](21-supabase-architecture.md) | ✅ Complete | PostgreSQL target schema, connection pooling, and RLS |
| 22 | [Firestore Architecture](22-firestore-architecture.md) | ✅ Complete | Alternative document-store adapter, transactions, and rules |
| 23 | [Data Migration Runbook](23-data-migration-runbook.md) | ✅ Complete | Step-by-step ETL runbook: SQLite to Supabase PostgreSQL |
| 24 | [UI/UX & Conversation Design](24-ui-ux-and-conversation-design.md) | ✅ Complete | Brand tone, message copy catalog, and accessibility |
| 25 | [Testing & Quality](25-testing-and-quality.md) | ✅ Complete | Testing pyramid, async fixtures, coverage gates, and load tests |
| 26 | [Performance & Concurrency](26-performance-and-concurrency.md) | ✅ Complete | Asyncio concurrency, memory budgets, and SLA latency targets |
| 27 | [Observability & Operations](27-observability-and-operations.md) | ✅ Complete | Structured JSON logging, privacy filters, metrics, and alerts |
| 28 | [Render Deployment](28-render-deployment.md) | ✅ Complete | `render.yaml` specification, persistent storage, and startup checks |
| 29 | [Free-Tier & Cost Model](29-free-tier-and-cost-model.md) | ✅ Complete | Quotas, unit economics, cost projections (0 to 50k DAU) |
| 30 | [CI/CD & Release Process](30-ci-cd-and-release-process.md) | ✅ Complete | GitHub Actions workflows, SemVer, and rollback procedures |
| 31 | [Configuration & Secrets](31-configuration-and-secrets.md) | ✅ Complete | Pydantic Settings, environment inventory, and rotation runbooks |
| 32 | [Backup & Recovery](32-backup-and-recovery.md) | ✅ Complete | RPO/RTO goals, online backup scripts, and disaster recovery |
| 33 | [Incident Response](33-incident-response.md) | ✅ Complete | Severity matrix, emergency kill switches, and postmortem guide |
| 34 | [Web & Mini App Future](34-web-and-mini-app-future.md) | ✅ Complete | Telegram WebApp `initData` auth, WebSockets, and cross-client |
| 35 | [Implementation Roadmap](35-implementation-roadmap.md) | ✅ Complete | Work breakdown structure, phase dependencies, and gates |
| 36 | [Acceptance Criteria](36-acceptance-criteria.md) | ✅ Complete | Definition of Done, Gherkin BDD specs, and benchmarks |
| 37 | [Risk Register](37-risk-register.md) | ✅ Complete | Risk heatmap, detailed risk inventory, and contingency plans |
| 38 | [Glossary](38-glossary.md) | ✅ Complete | Exhaustive domain, technical, Telegram, and security terms |
| 39 | [Architecture Decisions](39-architecture-decisions.md) | ✅ Complete | ADR log (ADR-001 through ADR-012) with full context |
| 40 | [Troubleshooting](40-troubleshooting.md) | ✅ Complete | Diagnostic cheatsheet, local dev and deployment resolutions |

---

## Architectural Conventions

- **DECIDED**: Finalized architecture decision implemented in blueprints.
- **PROPOSED**: Feature under technical consideration.
- **DEFERRED**: Intentionally postponed to post-MVP roadmap.
- **REJECTED**: Evaluated and discarded with documented rationale.
