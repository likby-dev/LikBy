# LikBy Technical Debt Ledger

**Last Audit:** 2026-10-17  
**Maintenance Level:** Active  

This document tracks intentional shortcuts, deferred architectural components, and technical debt items along with their risk assessment, justification, and remediation plans.

---

## 1. Active Technical Debt Items

### TD-01: In-Memory Game Session State in Local Mode
- **Component:** `src/likby/games/registry.py` & session managers
- **Description:** Active duel game turns are tracked in process memory for local execution. While durable match results are persisted to SQLite, active game boards would reset on server restart.
- **Risk:** Low during development; Medium if deployed to multi-worker or autoscaling environments.
- **Remediation Plan:** Move active session state to Redis / Firestore realtime document store before scaling beyond single-instance deployment.

### TD-02: Two-Phase Relational-to-Firestore Outbox Reliability
- **Component:** `src/likby/services/chat_relay_service.py`
- **Description:** Relational records (Supabase/SQLite) and Firestore chat documents cannot share an ACID transaction. If Firestore is unreachable during session initialization, the system queues a retry task.
- **Risk:** Low in SQLite mode; Medium under unstable network conditions with cloud Firestore.
- **Remediation Plan:** Implement a durable outbox table with idempotent worker sweeps (see `docs/data/DATA_CONSISTENCY.md`).

### TD-03: Render Free Tier Cold Starts
- **Component:** Deployment / Hosting (`render.yaml`)
- **Description:** Render free tier spins down after 15 minutes of idle time. The first webhook after spin-down incurs a 30-50 second delay.
- **Risk:** Degraded user experience on initial interaction.
- **Remediation Plan:** Transition to Render Starter ($7/month) or configure an external uptime monitor pinging `/health/live` every 10 minutes.

### TD-04: Test Deprecation Warning in Httpx
- **Component:** `tests/integration/test_payment_api.py`
- **Description:** Httpx emits a deprecation warning: `Use 'content=<...>' to upload raw bytes/text content` instead of `data=`.
- **Risk:** None currently (warning only); will fail in future major httpx release.
- **Remediation Plan:** Update test invocation syntax to `content=raw_payload`.
