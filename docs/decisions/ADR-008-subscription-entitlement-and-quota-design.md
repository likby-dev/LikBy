# ADR-008: Centralized Server-Side Subscription Entitlements & Quotas

- **Status:** Accepted & Implemented
- **Date:** 2026-10-15
- **Context:** Quota limits (Base: 20 uploads, 10 received, 3 searches, 5 duels) were previously dispersed across individual handlers, leading to inconsistencies.
- **Decision:** Centralize all quota accounting in `MediaQuotaService`, `SocialService`, and `SubscriptionService` with a strict `00:00:00 UTC` reset and atomic rollback on relay failure.
- **Alternatives Considered:** Client-side quota enforcement or handler-level counters.
- **Consequences:** 100% server-authoritative enforcement, race condition protection, and clean audit logs.
