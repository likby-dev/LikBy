# ADR-001: Local-First Zero-Credential Development

- **Status:** Accepted & Implemented
- **Date:** 2026-10-10
- **Context:** Developers and automated CI environments must be able to boot, run, and thoroughly test the application without depending on paid cloud services (Supabase, Firebase, Cloudflare).
- **Decision:** Use SQLite in WAL mode (`aiosqlite`) and a local filesystem directory (`media_store/`) as the default development environment.
- **Alternatives Considered:** Mandatory Docker Compose running local PostgreSQL and MinIO, or requiring staging cloud credentials.
- **Consequences:** Near-instant test execution (116 tests in ~22s), zero cloud setup friction for contributors. Production deployments must explicitly configure cloud providers.
