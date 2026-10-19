# AGENTS.md — Instructions for Autonomous & Coding Agents

Welcome to the **LikBy** codebase. This document outlines the mandatory operational conventions, architectural boundaries, coding standards, security guardrails, and testing requirements for all AI and human engineers working on this repository.

---

## 1. Product Identity & Core Mission

- **Canonical Product Name:** `LikBy` (or `LIKBY`).
- **Positioning:** *Meet. Connect. Play.* A privacy-first social discovery, relationship-building, and gaming platform starting Telegram-first with a shared FastAPI backend.
- **Legacy Aliases:** Naming in legacy branches or previous iterations may reference `Tikible`. Do not re-introduce `Tikible`. Standardize exclusively on `LikBy`.
- **Core Tenets:**
  1. **Non-Negotiable Persistence:** No self-destructing, ephemeral, or view-once messages. User media and conversation history persist until deliberate, authorized user deletion.
  2. **Zero-Advertising Policy:** No third-party advertisements, sponsored messages, or data monetization.
  3. **Content Protection:** All outbound Telegram media messages use `protect_content=True` to deter casual forwarding and saving. No fake DRM or false security claims.
  4. **Cost-Conscious Local-First:** Full functionality in local development using SQLite WAL mode and local file storage without requiring third-party cloud credentials.

---

## 2. System Architecture & Module Boundaries

The project is structured as a **modular monolith** with Clean Architecture / Hexagonal principles:

```
Telegram Client / Mini Apps / Future Web
                   │
                   ▼
       FastAPI Application (src/likby/main.py)
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
   API Endpoints      Telegram Adapters
(src/likby/api/)      (src/likby/telegram/)
        │                     │
        └──────────┬──────────┘
                   ▼
           Domain & Services
         (src/likby/services/ & src/likby/domain/)
                   │
                   ▼
         Persistence Interfaces
         (src/likby/repositories/)
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
   SQLite       Supabase    Firestore
  (Local)      (PostgreSQL) (Chat Store)
```

### Invariant Rules:
1. **Domain Isolation:** Core domain models and business services (`src/likby/domain/`, `src/likby/services/`) must **never** import or depend on Telegram SDK types (`aiogram`), FastAPI `Request` objects, or concrete third-party SDKs (`supabase`, `google.cloud.firestore`, `boto3`).
2. **Centralized Quota & Entitlement Authority:** Handlers must never independently calculate or grant quota or premium status. Always delegate to `MediaQuotaService`, `SocialService`, and `SubscriptionService`.
3. **No Silenced Cloud Downgrades:** In production (`APP_ENV=production`), missing cloud credentials must fail fast at startup. Never silently fallback to local ephemeral storage in production. In local development (`STORAGE_BACKEND=local`), no cloud credentials shall be required.

---

## 3. Subscription Tiers & Quota Catalog

The four authoritative tiers are:
1. **`base` (Free):**
   - Maximum 3 friends.
   - 3 discovery/people searches per day.
   - 5 duel-game plays per day with partners.
   - Unlimited solo games (zero duel quota consumption).
   - 20 media uploads per day (max 10MB per file).
   - 10 incoming/received media items per day.
2. **`spark` (24-Hour Temporary Pass):**
   - Earned via qualified referrals (1 spark pass per referral, rolling cap of 3 per 30 days) or purchased.
   - 5 friends, 25 searches/day, 10 duels/day, 40 uploads/day (max 25MB), 20 received/day.
3. **`premium` (30-Day Subscription):**
   - 15 friends, 100 searches/day, 25 duels/day, 100 uploads/day (max 50MB), 50 received/day.
   - Ability to see who liked your profile.
4. **`diamond` (30-Day VIP Subscription):**
   - 50 friends, 250 searches/day, 50 duels/day, 250 uploads/day (max 100MB), 100 received/day.
   - Priority matching and VIP badge.

**Daily Reset Rule:** All daily quotas reset strictly at `00:00:00 UTC`.

---

## 4. Games Catalog (12 Duels + 6 Solo)

All 18 games are registered in `src/likby/games/registry.py` and run server-authoritative logic:
- **12 Duel Games (turn-based / 2-player):**
  1. `connect_four` (Connect Four)
  2. `carrom_clash` (Carrom Clash)
  3. `air_rush` (Air Rush)
  4. `pocket_pool` (Pocket Pool)
  5. `stick_arena` (Stick Arena)
  6. `quickdraw` (Quickdraw)
  7. `word_rush` (Word Rush)
  8. `brain_blitz` (Brain Blitz)
  9. `reflex_rush` (Reflex Rush)
  10. `mindmatch` (MindMatch)
  11. `mystery_mission` (Mystery Mission)
  12. `xo` (XO Duel)
- **6 Solo Games (unlimited plays for Base tier):**
  1. `zen_merge` (Zen Merge)
  2. `word_hunt` (Word Hunt)
  3. `color_flow` (Color Flow)
  4. `pocket_golf` (Pocket Golf)
  5. `reflex_lab` (Reflex Lab)
  6. `daily_mystery` (Daily Mystery)

---

## 5. Security & DevSecOps Rules

1. **Zero Secrets in Git:** Never commit `.env` files, API keys, private keys, or tokens. `.env.example` must contain only dummy placeholder names.
2. **Authentication Proof:**
   - Webhooks: Authenticate with `X-Telegram-Bot-Api-Secret-Token`.
   - Mini Apps: Validate `initData` cryptographically using HMAC-SHA256 with the bot token. Never trust `initDataUnsafe`.
   - Razorpay Webhooks: Verify HMAC-SHA256 signature using `X-Razorpay-Signature` against the raw payload bytes.
   - Telegram Stars: Verify `pre_checkout_query` and handle `successful_payment` events server-side before activating subscriptions.
3. **Identifier Safety:** Never expose internal database auto-increment IDs or private storage paths. Always use public UUIDs or unique handles (`likby_id`).
4. **Path Traversal:** File archival uses SHA-256 hashed keys partitioned by prefix (`media/{hash[:2]}/{hash[2:4]}/{hash}.{ext}`). User-supplied filenames are never used as filesystem or object storage paths.

---

## 6. Coding & Testing Guidelines

- **Python Version:** Python 3.11+ (tested on Python 3.13).
- **Type Hints:** All function signatures must be fully type-annotated (`typing`).
- **Asyncio Everywhere:** Use non-blocking async handlers, repository calls, and HTTP clients (`httpx`, `aiosqlite`, `aiogram`).
- **Running Tests:**
  ```bash
  python -m pytest tests/ -v
  ```
- **Linting & Formatting:**
  ```bash
  python -m ruff check src/ tests/
  python -m ruff format --check src/ tests/
  ```
- **Never Break Existing Tests:** The test suite currently has 122 passing tests. Any change that causes a test regression must be rectified before submitting.

---

## 7. Migration & Database Conventions

- Relational migrations reside in `migrations/`.
  - `001_supabase_schema.sql`: Core PostgreSQL schema with foreign keys and indexes.
  - `002_rls_policies.sql`: Row Level Security policies.
  - `003_media_quotas_and_protection.sql`: Quota ledgers and size caps.
- SQLite is maintained in parity via SQLite repository implementations (`src/likby/repositories/sqlite/`).
- Do not execute destructive `DROP TABLE` operations on production without an ADR and a rollback migration script.
