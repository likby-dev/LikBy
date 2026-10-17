# ADR-003: Pure Domain and Repository Abstraction Boundaries

- **Status:** Accepted & Implemented
- **Date:** 2026-10-12
- **Context:** Business logic frequently gets coupled to specific database SDKs (Supabase, Firestore) or Telegram request objects.
- **Decision:** Enforce Clean Architecture boundaries. `src/likby/domain/` and `src/likby/services/` are pure Python and communicate with storage exclusively via abstract repository interfaces.
- **Alternatives Considered:** Tightly coupling SQL queries and Firestore DocumentReference calls directly within Telegram handlers.
- **Consequences:** Enables effortless switching between SQLite and Supabase/Firestore without altering core social or quota rules.
