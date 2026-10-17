# Changelog

All notable changes to the **LikBy** project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-10-17

### Added
- **Unified 17-Game Engine (`src/likby/games/`):**
  - Full server-authoritative rule engines for 11 Duel Games: Connect Four, Carrom Clash, Air Rush, Pocket Pool, Stick Arena, Quickdraw, Word Rush, Brain Blitz, Reflex Rush, MindMatch, and Mystery Mission.
  - Server engines for 6 Solo Games: Zen Merge, Word Hunt, Color Flow, Pocket Golf, Reflex Lab, and Daily Mystery.
  - Integration with Telegram Mini App (`/play`) and standalone HTML5/Canvas game clients.
- **Media Quotas & Dual Media Protection (`src/likby/services/media_quota_service.py`):**
  - Daily upload and receipt quota tracking per tier (Base: 20/10, Spark: 40/20, Premium: 100/50, Diamond: 250/100).
  - Maximum file size caps per tier (Base: 10MB, Spark: 25MB, Premium: 50MB, Diamond: 100MB).
  - Strict 00:00 UTC daily reset scheduler.
  - Two-phase quota reservation and atomic compensation rollback on delivery failure.
  - Strict `protect_content=True` on all Telegram media dispatches (`send_photo`, `send_video`, `send_voice`, `send_document`, `send_sticker`).
  - Strict zero-advertising policy and non-negotiable persistence (no self-destructing/ephemeral media).
- **Payment Providers:**
  - Telegram Stars native flow (`send_invoice`, `pre_checkout_query`, `successful_payment`, `/paysupport`).
  - Compliant out-of-Telegram Razorpay webhook adapter with HMAC-SHA256 signature verification.
- **Relational Migrations:**
  - `migrations/003_media_quotas_and_protection.sql` introducing `media_quota_events` and tier size limits.

### Changed
- Standardized canonical product name to **LikBy** across all documentation, tests, and source modules.
- Refactored Telegram bot entry points and FastAPI lifespan into `src/likby/main.py`.
- Updated test suite to 116 unit and integration tests with 100% pass rate.

---

## [1.1.0] - 2026-10-15

### Added
- **Multi-Store Architecture:**
  - SQLite WAL mode for local-first zero-credential development.
  - Supabase PostgreSQL relational schemas (`migrations/001_supabase_schema.sql`, `migrations/002_rls_policies.sql`).
  - Firebase Firestore session and transcript adapter for chat persistence.
  - Cloudflare R2 media storage adapter specification with local directory fallback.
- **Social & Matching Engine:**
  - Compatibility scoring algorithm based on age, gender preference, and shared languages.
  - Matchmaking queue with ticket state management.
  - Referral system granting 24-hour Spark passes with rolling 30-day anti-abuse limits.

---

## [1.0.0] - 2026-10-10

### Initial Architecture & Prototype
- Initial Telegram bot prototype with user onboarding, profile setup, and basic matchmaking.
- Clean Architecture repository pattern with Pydantic settings.
- SQLite initial database support.
