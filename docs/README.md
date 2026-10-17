# LikBy Master Documentation Catalog

Welcome to the comprehensive technical documentation for **LikBy** (*Meet. Connect. Play.*). This catalog organizes the architecture, security, product specifications, operations runbooks, and implementation status for the entire platform.

---

## 1. Documentation Map & Navigation

```
docs/
├── architecture/       <- High-level & component architecture, contracts, and data flows
├── audit/              <- Codebase audit, implementation status, and technical debt
├── research/           <- Telegram Bot API features, limits, and cloud pricing
├── product/            <- PRD, user journeys, quotas, entitlements, and privacy
├── features/           <- Core social discovery, matching, chat, media, 17 games, referrals
├── telegram/           <- Telegram UX system, keyboards, messaging design
├── data/               <- Storage ownership matrix, SQLite, Supabase, Firestore, R2
├── security/           <- Threat model (STRIDE), webhook security, media protection
├── testing/            <- Test strategy, automated test catalogs, quality gates
├── deployment/         <- Local-first setup, environment variables, Render blueprint
├── operations/         <- Standard operating runbooks, incident response, cost model
├── runbooks/           <- Dedicated emergency recovery runbooks
├── ai-ml/              <- AI/ML strategy, guardrails, and privacy
├── payments/           <- Telegram Stars native flow & compliant Razorpay adapter
└── decisions/          <- Architecture Decision Records (ADR-001 through ADR-010)
```

---

## 2. Document Index by Category

### 2.1 Architecture (`docs/architecture/`)
- [SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md) — High-level modular monolith and Clean Architecture design.
- [COMPONENT_ARCHITECTURE.md](architecture/COMPONENT_ARCHITECTURE.md) — Subsystem boundaries and layer interactions.
- [DATA_FLOW.md](architecture/DATA_FLOW.md) — End-to-end sequence diagrams for matching and media relay.
- [RELATIONSHIP_MODEL.md](architecture/RELATIONSHIP_MODEL.md) — Entity-relationship diagram and referential integrity constraints.
- [API_CONTRACTS.md](architecture/API_CONTRACTS.md) — FastAPI endpoints, Mini App gaming APIs, and webhook contracts.
- [SCALABILITY_AND_FAILURE_MODES.md](architecture/SCALABILITY_AND_FAILURE_MODES.md) — Concurrency models, flood control, and circuit breakers.
- [ARCHITECTURE_GLOSSARY.md](architecture/ARCHITECTURE_GLOSSARY.md) — Canonical definitions and product terminology.

### 2.2 Audit & Implementation (`docs/audit/`)
- [REPOSITORY_AUDIT.md](audit/REPOSITORY_AUDIT.md) — Complete repository audit and severity findings.
- [IMPLEMENTATION_STATUS.md](audit/IMPLEMENTATION_STATUS.md) — Authoritative requirement verification matrix.
- [TECHNICAL_DEBT.md](audit/TECHNICAL_DEBT.md) — Tracked technical debt, rationale, and remediation roadmap.
- [MIGRATION_PLAN.md](audit/MIGRATION_PLAN.md) — Step-by-step production cutover plan.

### 2.3 Research (`docs/research/`)
- [TELEGRAM_FEATURE_RESEARCH.md](research/TELEGRAM_FEATURE_RESEARCH.md) — Feature evaluation matrix for Telegram Bot API.
- [PLATFORM_LIMITS_AND_PRICING.md](research/PLATFORM_LIMITS_AND_PRICING.md) — Official limits and pricing for Telegram, Render, Supabase, Firestore, R2.

### 2.4 Product & Requirements (`docs/product/`)
- [PRODUCT_REQUIREMENTS.md](product/PRODUCT_REQUIREMENTS.md) — Product requirements document (PRD) and core personas.
- [USER_JOURNEYS.md](product/USER_JOURNEYS.md) — Detailed user walkthroughs (onboarding, chat, games, upgrades).
- [SUBSCRIPTION_ENTITLEMENTS.md](product/SUBSCRIPTION_ENTITLEMENTS.md) — Detailed quota comparison for Base, Spark, Premium, and Diamond.
- [QUOTA_POLICY.md](product/QUOTA_POLICY.md) — Two-phase quota reservation, rollback, and 00:00 UTC reset rules.
- [NOTIFICATION_POLICY.md](product/NOTIFICATION_POLICY.md) — Category priorities, anti-spam, and quiet hours.
- [PRIVACY_AND_USER_CONTROLS.md](product/PRIVACY_AND_USER_CONTROLS.md) — Privacy toggles, blocking, and account erasure.

### 2.5 Features (`docs/features/` & `docs/telegram/`)
- [PROFILE_AND_DISCOVERY.md](features/PROFILE_AND_DISCOVERY.md) — Profile attributes, age verification, and compatibility scorer.
- [MATCHING_AND_FRIENDSHIP.md](features/MATCHING_AND_FRIENDSHIP.md) — Social state machine and friend capacity limits.
- [CHAT_AND_MEDIA.md](features/CHAT_AND_MEDIA.md) — Media sharing, `protect_content=True`, and non-negotiable persistence.
- [GAMES_CATALOG.md](features/GAMES_CATALOG.md) — Complete specifications for all 11 Duel Games and 6 Solo Games.
- [REFERRALS.md](features/REFERRALS.md) — Deep link attribution, anti-fraud rules, and 24h Spark rewards.
- [TELEGRAM_UX_SYSTEM.md](telegram/TELEGRAM_UX_SYSTEM.md) — UI design system, message formatting, and keyboard hierarchies.

### 2.6 Data & Storage (`docs/data/`)
- [DATA_OWNERSHIP_MATRIX.md](data/DATA_OWNERSHIP_MATRIX.md) — Division of responsibility between SQLite, Supabase, Firestore, and R2.
- [LOCAL_STORAGE.md](data/LOCAL_STORAGE.md) — SQLite WAL mode and local filesystem configuration.
- [SUPABASE_SCHEMA.md](data/SUPABASE_SCHEMA.md) — PostgreSQL schema reference, foreign keys, and indexes.
- [FIRESTORE_SCHEMA.md](data/FIRESTORE_SCHEMA.md) — Document hierarchy and security rules for chat sessions.
- [MEDIA_STORAGE_AND_ACCESS.md](data/MEDIA_STORAGE_AND_ACCESS.md) — Dual storage strategy: Telegram file_id + R2 archival.
- [DATA_CONSISTENCY.md](data/DATA_CONSISTENCY.md) — Cross-store outbox pattern and idempotency.
- [DATA_MIGRATION_RUNBOOK.md](data/DATA_MIGRATION_RUNBOOK.md) — SQLite to Supabase ETL runbook.
- [BACKUP_AND_RECOVERY.md](data/BACKUP_AND_RECOVERY.md) — RPO/RTO goals and snapshot schedules.
- [DATA_RETENTION_AND_DELETION.md](data/DATA_RETENTION_AND_DELETION.md) — Data lifecycle and GDPR compliance.

### 2.7 Security (`docs/security/`)
- [THREAT_MODEL.md](security/THREAT_MODEL.md) — STRIDE threat analysis and verified mitigations.
- [SECURE_CONFIGURATION.md](security/SECURE_CONFIGURATION.md) — Environment variable management and fail-fast validation.
- [TELEGRAM_WEBHOOK_SECURITY.md](security/TELEGRAM_WEBHOOK_SECURITY.md) — Webhook secret token authentication.
- [MEDIA_SECURITY.md](security/MEDIA_SECURITY.md) — Content protection and SHA-256 key hashing.
- [DATABASE_SECURITY.md](security/DATABASE_SECURITY.md) — Supabase RLS and filesystem hardening.
- [PAYMENT_SECURITY.md](security/PAYMENT_SECURITY.md) — Telegram Stars verification and Razorpay HMAC checks.
- [ABUSE_PREVENTION.md](security/ABUSE_PREVENTION.md) — Blocking, reporting, and karma engine.
- [PRIVACY_AND_CONSENT.md](security/PRIVACY_AND_CONSENT.md) — Zero advertising and non-negotiable persistence guarantees.

### 2.8 Testing & Quality (`docs/testing/`)
- [TEST_STRATEGY.md](testing/TEST_STRATEGY.md) — Testing pyramid and async test execution.
- [TEST_CASES.md](testing/TEST_CASES.md) — Comprehensive catalog of 116 passed unit and integration tests.
- [SECURITY_TESTING.md](testing/SECURITY_TESTING.md) — Automated security attack vector test suite.
- [PROVIDER_CONTRACT_TESTING.md](testing/PROVIDER_CONTRACT_TESTING.md) — Storage repository interface contracts.
- [RELEASE_QUALITY_GATES.md](testing/RELEASE_QUALITY_GATES.md) — Pre-deployment test, lint, and formatting gates.

### 2.9 Deployment, Operations & Runbooks (`docs/deployment/`, `docs/operations/`, `docs/runbooks/`)
- [LOCAL_DEVELOPMENT.md](deployment/LOCAL_DEVELOPMENT.md) — Frictionless zero-cloud local development setup.
- [ENVIRONMENT_VARIABLES.md](deployment/ENVIRONMENT_VARIABLES.md) — Comprehensive environment variable specification.
- [RENDER_DEPLOYMENT.md](deployment/RENDER_DEPLOYMENT.md) — Render Web Service deployment and blueprint guide.
- [PRODUCTION_READINESS.md](deployment/PRODUCTION_READINESS.md) — Launch readiness checklist.
- [CLOUD_MIGRATION.md](deployment/CLOUD_MIGRATION.md) — Guidance for switching to managed cloud infrastructure.
- [RUNBOOK.md](operations/RUNBOOK.md) — Standard operating procedures and health checks.
- [INCIDENT_RESPONSE.md](operations/INCIDENT_RESPONSE.md) — Severity classifications and emergency kill-switch.
- [OBSERVABILITY.md](operations/OBSERVABILITY.md) — Structured JSON logging and privacy filters.
- [COST_MANAGEMENT.md](operations/COST_MANAGEMENT.md) — Free-tier optimization and cost curves.
- [DATABASE_RECOVERY.md](runbooks/DATABASE_RECOVERY.md) — Recovery procedures for SQLite and Supabase.
- [FAILED_WEBHOOK_RECOVERY.md](runbooks/FAILED_WEBHOOK_RECOVERY.md) — Webhook failure troubleshooting.
- [MEDIA_STORAGE_RECOVERY.md](runbooks/MEDIA_STORAGE_RECOVERY.md) — Cloudflare R2 connectivity recovery.
- [PAYMENT_RECONCILIATION.md](runbooks/PAYMENT_RECONCILIATION.md) — Stars and Razorpay payment audit runbook.

### 2.10 AI/ML & Payments (`docs/ai-ml/`, `docs/payments/`)
- [AI_ML_STRATEGY.md](ai-ml/AI_ML_STRATEGY.md) — Deterministic core with optional AI icebreakers.
- [AI_PRIVACY_AND_EVALUATION.md](ai-ml/AI_PRIVACY_AND_EVALUATION.md) — Zero external data training and model evaluation.
- [PAYMENT_ARCHITECTURE.md](payments/PAYMENT_ARCHITECTURE.md) — Dual payment architecture: Telegram Stars vs Web Razorpay.
- [TELEGRAM_STARS.md](payments/TELEGRAM_STARS.md) — Native Telegram Stars lifecycle and compliance.
- [RAZORPAY_SCOPE_AND_COMPLIANCE.md](payments/RAZORPAY_SCOPE_AND_COMPLIANCE.md) — Compliant out-of-Telegram Razorpay verification.

### 2.11 Architecture Decisions (`docs/decisions/`)
- [ADR-001: Local-First Zero-Credential Development](decisions/ADR-001-local-first-development.md)
- [ADR-002: Shared FastAPI Backend for Bot and Future Clients](decisions/ADR-002-shared-fastapi-backend.md)
- [ADR-003: Pure Domain and Repository Abstraction Boundaries](decisions/ADR-003-domain-and-repository-boundaries.md)
- [ADR-004: Supabase PostgreSQL as Canonical Relational Source of Truth](decisions/ADR-004-supabase-relational-ownership.md)
- [ADR-005: Firebase Cloud Firestore for Chat Sessions and Transcripts](decisions/ADR-005-firestore-conversation-ownership.md)
- [ADR-006: Cloudflare R2 for Durable Media Object Storage](decisions/ADR-006-cloudflare-r2-media-storage.md)
- [ADR-007: Dual Telegram Update Reception (Polling vs Webhook)](decisions/ADR-007-telegram-update-reception-modes.md)
- [ADR-008: Centralized Server-Side Subscription Entitlements & Quotas](decisions/ADR-008-subscription-entitlement-and-quota-design.md)
- [ADR-009: Telegram Stars Native In-App Payments & Razorpay Separation](decisions/ADR-009-telegram-stars-and-payment-compliance.md)
- [ADR-010: Deterministic Guardrails and Optional AI Enhancements](decisions/ADR-010-ai-ml-scope-and-guardrails.md)
