# ADR-006: Cloudflare R2 for Durable Media Object Storage

- **Status:** Accepted & Prepared
- **Date:** 2026-10-14
- **Context:** Telegram `file_id` references may expire or be inaccessible outside Telegram. User media must be archived durably without incurring massive egress fees.
- **Decision:** Use Cloudflare R2 as the persistent media object store, leveraging its S3-compatible API and **zero egress fee** model.
- **Alternatives Considered:** AWS S3 (costly egress bandwidth) or Supabase Storage (bandwidth caps on free tier).
- **Consequences:** Highly cost-effective media archiving with deterministic SHA-256 content-addressed keys.
