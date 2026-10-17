# ADR-002: Shared FastAPI Backend for Bot and Future Clients

- **Status:** Accepted & Implemented
- **Date:** 2026-10-10
- **Context:** The product starts Telegram-first but will expand to Telegram Mini Apps and a public web client. Business rules must not be duplicated across platforms.
- **Decision:** Use FastAPI as the single unified backend. The Telegram bot is mounted within FastAPI's lifespan (supporting polling and webhooks), and Mini Apps communicate via the same REST APIs.
- **Alternatives Considered:** Standalone aiogram process separate from FastAPI backend.
- **Consequences:** Single deployment unit on Render, unified health checks and metrics, reusable domain services.
