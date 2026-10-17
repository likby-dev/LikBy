# ADR-005: Firebase Cloud Firestore for Chat Sessions and Transcripts

- **Status:** Accepted & Prepared
- **Date:** 2026-10-13
- **Context:** Chat messaging is high-volume, append-only, and requires real-time listener capabilities and structured session documents.
- **Decision:** Assign Firebase Cloud Firestore ownership of chat sessions and message transcripts under `/chat_sessions/{session_id}/messages`.
- **Alternatives Considered:** Storing millions of chat messages in PostgreSQL tables.
- **Consequences:** High write throughput and native document hierarchy; requires outbox pattern for cross-store consistency with PostgreSQL.
