# ADR-004: Supabase PostgreSQL as Canonical Relational Source of Truth

- **Status:** Accepted & Prepared
- **Date:** 2026-10-13
- **Context:** Structured entities such as user accounts, profiles, mutual matches, subscription entitlements, and financial transaction logs require strict ACID guarantees and relational constraints.
- **Decision:** Assign Supabase PostgreSQL authoritative ownership over all core relational entities and quota audit ledgers.
- **Alternatives Considered:** Storing everything in Firebase Firestore as a single document database.
- **Consequences:** Guaranteed referential integrity, strong unique handle constraints, and reliable financial ledgers.
