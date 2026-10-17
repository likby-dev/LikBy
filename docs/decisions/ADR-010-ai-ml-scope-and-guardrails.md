# ADR-010: Deterministic Guardrails and Optional AI Enhancements

- **Status:** Accepted & Implemented
- **Date:** 2026-10-16
- **Context:** Relying on LLMs for core social logic, quotas, or matching introduces non-deterministic failure modes and vendor dependencies.
- **Decision:** Keep core matching, quotas, and safety rules 100% deterministic code. Restrict AI to optional, user-invoked features (icebreaker suggestions, bio polishing) with zero training on user chat data.
- **Alternatives Considered:** LLM-driven autonomous matchmaking and conversational agents.
- **Consequences:** Zero single-point-of-failure risks, low operating costs, and ironclad privacy guarantees.
