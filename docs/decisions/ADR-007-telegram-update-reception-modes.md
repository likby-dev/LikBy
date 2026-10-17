# ADR-007: Dual Telegram Update Reception (Polling vs Webhook)

- **Status:** Accepted & Implemented
- **Date:** 2026-10-14
- **Context:** Local development behind NAT/firewalls cannot receive direct HTTPS webhooks without tunnels, while production requires webhook scalability.
- **Decision:** Support both modes via `TELEGRAM_MODE`: `polling` for local development and `webhook` for production on Render.
- **Alternatives Considered:** Mandatory ngrok tunnels for local development.
- **Consequences:** Frictionless local testing while maintaining high-throughput webhook reception in production.
