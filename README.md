# LikBy 💙 — Meet. Connect. Play.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![aiogram](https://img.shields.io/badge/aiogram-3.15%2B-2CA5E0.svg)](https://docs.aiogram.dev/)
[![Supabase Postgres](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E.svg)](https://supabase.com/)
[![Firebase Firestore](https://img.shields.io/badge/Firebase-Cloud%20Firestore-FFCA28.svg)](https://firebase.google.com/)
[![Cloudflare R2](https://img.shields.io/badge/Cloudflare%20R2-S3%20Compatible-F38020.svg)](https://developers.cloudflare.com/r2/)
[![Render](https://img.shields.io/badge/Render-Deployment%20Ready-46E3B7.svg)](https://render.com/)
[![Tests Passing](https://img.shields.io/badge/Tests-122%2F122%20Passing-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

> **LikBy** (*Meet. Connect. Play.*) is a premium, privacy-first Telegram social discovery, matching, and 17-game multiplayer platform powered by a shared FastAPI backend.
> Live Telegram Bot: [@LikBy_bot](https://t.me/LikBy_bot) | [Full Documentation Catalog](docs/README.md)

---

## 📑 Table of Contents

- [1. Product Overview](#1-product-overview)
- [2. System Architecture](#2-system-architecture)
- [3. Technology Allocation & Authority Rules](#3-technology-allocation--authority-rules)
- [4. Core System Flows](#4-core-system-flows)
  - [4.1 Message Ingestion & Delivery Pipeline](#41-message-ingestion--delivery-pipeline)
  - [4.2 Standardized Human-Readable Chat Transcript](#42-standardized-human-readable-chat-transcript)
  - [4.3 Mutual Likes & Canonical Friendship Lifecycle](#43-mutual-likes--canonical-friendship-lifecycle)
  - [4.4 Discovery, Search Quotas & Connection Requests](#44-discovery-search-quotas--connection-requests)
  - [4.5 Reputation, Ratings & Auditable Karma Ledger](#45-reputation-ratings--auditable-karma-ledger)
  - [4.6 Centralized Subscription & Entitlement Engine](#46-centralized-subscription--entitlement-engine)
- [5. Database Schema & Storage Design](#5-database-schema--storage-design)
- [6. Configuration & Environment Variables](#6-configuration--environment-variables)
- [7. Local Development Quickstart](#7-local-development-quickstart)
- [8. Testing & QA Automation](#8-testing--qa-automation)
- [9. Production Deployment Guide (Render)](#9-production-deployment-guide-render)
- [10. Architecture Documentation Index](#10-architecture-documentation-index)

---

## 1. Product Overview

LikBy provides a safe, welcoming, and privacy-respecting environment where adults can discover interesting people, chat anonymously in real time, build friendships, and play casual games.

### Key Value Propositions
* 🔒 **Zero Contact Leakage:** Phone numbers, Telegram handles, and locations are strictly protected. Users choose a permanent unique ID (e.g. `@cryptowizard` or `LK-10001`) and a customizable display name.
* 💬 **Durable Session Chat Engine:** Real-time message and media forwarding with strict per-session ordering, outbox pattern failure recovery, and on-demand `.txt` transcript exports.
* 💙 **Mutual-Like Friendships:** Express interest after a chat session. If both users like each other, an atomic canonical friendship is established.
* 🌟 **Transparent Karma System:** Post-session ratings (+1 Like / -1 Dislike) feed into an immutable, auditable karma ledger with net-contribution reversal protection.
* 🛡️ **Responsible Moderation:** Bilateral blocking and evidence logging without unverified automated karma penalties.
* 🕹️ **Casual Solo Arcade & Multiplayer:** 17 games including Trivia Blitz, Gem Hunter, Connect Four, Air Rush, and Stick Arena.

---

## 2. System Architecture

LikBy implements a **modular monolith** with clear service boundaries and authoritative separation of concerns:

```mermaid
graph TD
    subgraph Client Layer
        TG[Telegram Mobile / Desktop / Web Client]
    end

    subgraph Entrypoint & Adapter Layer
        WH[FastAPI Webhook: /api/v1/telegram/webhook]
        POL[Long Polling Runner: python -m likby.main --mode polling]
        DP[aiogram 3 Dispatcher & Routers]
    end

    subgraph Domain & Application Services
        CR[ChatRelayService]
        MM[MatchmakingService]
        SOC[SocialService]
        DISC[DiscoveryService]
        KRM[KarmaService]
        SUB[SubscriptionService]
        TRN[TranscriptService]
        MED[MediaService]
        OBW[OutboxWorker]
        REC[ReconciliationService]
    end

    subgraph Persistence & Infrastructure
        SUPABASE[(Supabase PostgreSQL: Users, Relational State, Quotas, Outbox)]
        FIRESTORE[(Firebase Cloud Firestore: Ordered Chat Messages & Session Events)]
        R2[(Cloudflare R2: S3-Compatible Encrypted Private Media Storage)]
        TG_API[Telegram Bot HTTP API]
    end

    TG -->|Updates| WH
    TG -->|Updates| POL
    WH --> DP
    POL --> DP

    DP --> CR
    DP --> MM
    DP --> SOC
    DP --> DISC
    DP --> KRM
    DP --> SUB

    CR --> FIRESTORE
    CR --> SUPABASE
    CR --> MED
    MED --> R2
    
    OBW --> SUPABASE
    OBW -->|Async Delivery| TG_API
    REC --> SUPABASE
    REC --> FIRESTORE
    REC --> R2
```

---

## 3. Technology Allocation & Authority Rules

| Component | Technology | Authoritative Responsibility |
| :--- | :--- | :--- |
| **API & Orchestration** | FastAPI | Validation, business workflows, authentication, rate limits, and service coordination |
| **Relational Database** | Supabase PostgreSQL | Users, subscriptions, friendships, likes, quotas, ratings, karma, reports, assets metadata, and outbox jobs |
| **Conversation Database** | Firebase Cloud Firestore | Chat message documents, ordered conversation events, and reconstructable chat history |
| **Binary Media Storage** | Cloudflare R2 | Actual photos, videos, voice notes, and documents in private buckets with short-lived presigned URLs |
| **Durable Cross-Service Work** | PostgreSQL Outbox & Workers | Pending operations, exponential retry backoff with jitter, dead-lettering, and reconciliation |
| **Local Development** | SQLite WAL / Mock Adapters | Rapid hermetic local testing; never a competing production source of truth |
| **Deployment** | Render | Managed FastAPI web service (`likby-app`) and background worker service (`likby-worker`) |

---

## 3. Core System Flows

### 3.1 Message Ingestion & Delivery Pipeline

Every message relayed through an active chat session follows an outbox-backed delivery lifecycle:

```mermaid
sequenceDiagram
    autonumber
    actor Alice as User A (Telegram)
    participant Bot as LikBy Bot Dispatcher
    participant Relay as ChatRelayService
    participant Repo as MessageRepository
    participant TG as Telegram Bot API
    participant Outbox as OutboxRepository
    actor Bob as User B (Telegram)

    Alice->>Bot: Sends Text / Media Message
    Bot->>Relay: relay_text(sender_tg_id, text)
    Relay->>Relay: Resolve active session & partner ID
    Relay->>Repo: get_next_sequence(session_id)
    Relay->>Repo: save(ChatMessage[status=PENDING, sequence=N])
    
    alt Successful Delivery
        Relay->>TG: send_message(chat_id=Bob_TG_ID, text)
        TG-->>Bob: Delivered to Bob
        TG-->>Relay: OK (telegram_message_id)
        Relay->>Repo: update_delivery_status(DELIVERED, tg_msg_id)
    else Transient Failure / Rate Limit
        Relay->>TG: send_message(...) -> Error
        Relay->>Repo: update_delivery_status(FAILED)
        Relay->>Outbox: save(OutboxJob[status=PENDING, next_attempt_at=now+backoff])
    end
```

---

### 3.2 Standardized Human-Readable Chat Transcript

LikBy does not require users or support staff to parse raw JSON message objects. The `TranscriptService` and `TranscriptFormatter` generate standardized plain text `.txt` documents on demand:

```text
LIKBY CHAT SESSION
Session ID: cs_01K8XYZ...
Started: 2026-10-16 12:30:00 UTC

Participants:
User A (ID: LK-10001)
User B (ID: LK-10002)

[12:30:01] User A (LK-10001): Hi!
[12:30:05] User B (LK-10002): Hello!
[12:30:12] User A (LK-10001): How was your day?
[12:30:20] User B (LK-10002): It was great!
[12:30:25] User A (LK-10001): [PHOTO: ast_01K8DEF_photo.jpg]
[12:31:00] SYSTEM: Session reported.
[12:31:05] SYSTEM: Report submitted for review.

Session Status: ENDED
```

---

### 3.3 Mutual Likes & Canonical Friendship Lifecycle

Directional likes and friendships are separate entities. Friendships use canonical pairs `frd_{min(u1, u2)}_{max(u1, u2)}` to eliminate duplicates:

```mermaid
stateDiagram-v2
    [*] --> DirectionalLike: User A likes User B
    DirectionalLike --> PendingReciprocal: B has not liked A yet
    PendingReciprocal --> WhoLikedMe: Visible in B's "Who Liked Me"
    
    WhoLikedMe --> CapacityCheck: B taps [Like Back]
    state CapacityCheck {
        [*] --> CheckSenderCapacity
        CheckSenderCapacity --> CheckTargetCapacity: A friends < max_friends
        CheckTargetCapacity --> Eligible: B friends < max_friends
        CheckTargetCapacity --> Ineligible: B at limit
        CheckSenderCapacity --> Ineligible: A at limit
    }
    
    Eligible --> ActiveFriendship: Create frd_{min}_{max}
    Ineligible --> PendingCapacity: Like saved, upgrade required
    ActiveFriendship --> Removed: remove_friend()
    ActiveFriendship --> Blocked: User blocks partner
    Removed --> [*]
    Blocked --> [*]
```

---

### 3.4 Discovery, Search Quotas & Connection Requests

1. **Format Validation:** Query can be a permanent handle (`@username`) or internal user ID.
2. **Quota Check:** Server verifies daily quota against `SubscriptionEntitlement` and atomic counter `DailyUsage`. Free tier permits 3 searches/day.
3. **Privacy Filter:** Only public display ID and coarse activity state (`Active recently`, `Inactive`, `Hidden`) are returned.
4. **Connection Invitation:** Requester can send a `ConnectionRequest`. When accepted, both users' friend limits are verified before atomically establishing friendship.

---

### 3.5 Reputation, Ratings & Auditable Karma Ledger

* **Good Chat (Like):** `+1` karma.
* **Poor Chat (Dislike):** `-1` karma.
* **Rating Reversal:** If User A changes their rating from Like to Dislike, the system applies `new_delta - old_delta = (-1) - (+1) = -2` net delta.
* **Audit Trail:** Every point adjustment creates an immutable `KarmaLedgerEntry` with a unique idempotency key preventing double execution.
* **Non-Punitive Reporting:** Filing an abuse report immediately applies a bilateral block and notifies moderators, but **does not deduct karma** until verified by a human moderator.

---

### 3.6 Centralized Subscription & Entitlement Engine

| Feature | LIKBY_BASE | LIKBY_SPARK | LIKBY_PREMIUM | LIKBY_DIAMOND |
| :--- | :---: | :---: | :---: | :---: |
| **Daily Multiplayer Duels** | **5** / day | **10** / day | **25** / day | **Unlimited** 👑 |
| **Solo Games** | **Unlimited** | **Unlimited** | **Unlimited** | **Unlimited** |
| **Game Catalogue** | **All 17** | **All 17** | **All 17** | **All 17** |
| **Max Concurrent Friends** | **3** | **10** | **25** | **100** |
| **Daily ID Searches** | **3** / day | **20** / day | **50** / day | **100** / day |
| **Daily Connection Requests** | **5** / day | **25** / day | **50** / day | **100** / day |

> **Downgrade Safety:** Expired subscriptions automatically revert feature quotas to the Base tier, but **never delete existing friendships**.

---

### 3.7 LikBy Play — Telegram Multiplayer & Solo Gaming Ecosystem

LikBy Play is a premium social gaming ecosystem built directly into Telegram and Telegram Mini Apps with the core philosophy: *"Every connection has a game."*

#### 17 Complete Game Experiences

* **11 Multiplayer Duel Games:**
  1. 🥇 **Carrom Clash** — Physics-based carrom board with striker aiming, power control, coin collisions, and queen rules.
  2. 🏒 **Air Rush** — High-speed arcade air hockey with responsive paddles, puck physics, and 5-goal target condition.
  3. 🎱 **Pocket Pool** — 8-ball billiards with cue ball aiming, collision physics, solids vs. stripes tracking, and pocketing rules.
  4. ⚔️ **Stick Arena** — 2D platform brawler with jump/dodge mechanics, light/heavy attacks, knockback, and health bars.
  5. 🎨 **QuickDraw** — Real-time drawing canvas synchronization with secret word bank and server-side guess evaluation.
  6. 🔤 **Word Rush** — Shared letter sets and word chains with server-side dictionary verification and streak scoring.
  7. 🧠 **Brain Blitz** — Fast-paced trivia quiz with curated categories, question timers, and answer hiding until submission.
  8. ⚡ **Reflex Rush** — Server-scheduled millisecond visual cue competition with false-start detection.
  9. 🔵 **Connect Four** — Strategic 7x6 four-in-a-row board with turn validation and win/draw detection.
  10. 💭 **MindMatch** — Social dilemma matching ("Beach Sunset" vs. "Mountain Cabin") with simultaneous reveal and harmony scoring.
  11. 🕵️ **Mystery Mission** — Cooperative deduction puzzle with partitioned clues (Clue A for P1, Clue B for P2) and stage progression.

* **6 Solo Casual Games (Unlimited for All Tiers):**
  12. 🧩 **Zen Merge** — 4x4 sliding number tile puzzle with smooth swipe mechanics and high-score tracking.
  13. 🔎 **Word Hunt** — Hidden word grid matrix with multi-directional word selection and hints.
  14. 🎨 **Color Flow** — Color and logic flow puzzle with non-overlapping color connections.
  15. ⛳ **Pocket Golf** — Mini-golf putting green with drag-to-aim power meter and obstacle collision physics.
  16. ⚡ **Reflex Lab** — Quick reaction and sequence memory training with casual score metrics.
  17. 🔐 **Daily Mystery** — Logic riddle puzzle with clue checklist, hint mechanics, and answer validation.

#### Authoritative Quota & Fairness Rules
* **Strict Server-Side Enforcement:** Daily quotas are enforced via FastAPI and PostgreSQL/SQLite transactions; clients cannot manipulate counters via localStorage or cookies.
* **Asia/Kolkata Daily Boundary:** Quotas calculate against an explicit `Asia/Kolkata` midnight reset window, persisted in UTC.
* **Atomic Dual-Credit Reservation:** Starting an active duel atomically checks both players' remaining allowances and reserves 1 credit each. If either player lacks credits, the duel is cleanly rejected.
* **Zero Solo Consumption:** Solo games never consume duel credits (0 credits consumed).
* **Invitation Protection:** Failed, rejected, or expired game challenges consume zero credits.
* **Rematch Policy:** Each rematch is an authoritative new match and consumes 1 credit per player.

#### Telegram Mini App Integration
* **Bot Entrypoints:** `/play`, `/games`, `/duels`, `/solo`, `/mygames`.
* **Mini App WebApp:** Served statically at `/play/` with dark brand theme (`#050816`), cyan/blue accents, responsive viewport, and audio synth.
* **HMAC-SHA256 Security:** Raw Telegram `initData` is verified server-side with HMAC-SHA256 signature against the bot token.
* **Realtime WebSockets:** Live events delivered at `/api/v1/play/ws/{session_id}`.

---

## 4. Technology Stack & Component Boundaries

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Runtime & Language** | Python 3.11+ / 3.13 | High performance, modern async/await syntax, strong typing |
| **Web Server** | FastAPI & Uvicorn | Production ASGI server for webhooks, WebSockets, and health endpoints |
| **Telegram Framework** | aiogram 3.15+ | Modern async Telegram Bot API framework with clean routing & FSM |
| **Telegram Mini App** | HTML5 / Vanilla CSS / ES6 JS | Lightweight, ultra-responsive Telegram WebApp lobby and 17 interactive games |
| **Database** | SQLite WAL / Supabase PostgreSQL | High-concurrency ACID transactions for quota reservations and game states |
| **Cloud Storage** | Cloudflare R2 (S3-compatible) | Zero egress fee object storage for encrypted media archival |
| **Data Validation** | Pydantic v2 | Strict schema validation and immutable domain entity modeling |
| **Test Automation** | pytest & pytest-asyncio | 122 unit, integration, and API tests with 100% pass rate |

---

## 5. Database Schema & Storage Design

The database schema (`src/likby/repositories/sqlite/database.py`) enforces referential integrity:

1. `users` — Account standing, karma score, verification state, immutable handle.
2. `profiles` — Non-unique display names, age, gender, interests.
3. `chat_sessions` — Active and archived chat pairings with metadata.
4. `messages` — Durable chat messages with strict per-session ordering sequence.
5. `media_assets` — S3/R2 storage references, SHA-256 integrity hashes, MIME types.
6. `likes` — Directional social interest records with unique `(sender_id, target_id)`.
7. `friendships` — Canonical mutual relationships with key `frd_{min}_{max}`.
8. `connection_requests` — Discovery connection invitations and lifecycle state.
9. `session_ratings` — Post-session like/dislike evaluations per session participant.
10. `karma_ledger` — Immutable audit ledger of all reputation score adjustments.
11. `subscriptions` — Evaluated tier standing and quota parameters.
12. `daily_usage` — Daily search and connection request consumption counters.
13. `outbox_jobs` — Transactional message delivery queue with retry timestamps.
14. `reports` & `user_blocks` — Abuse reports and bilateral safety blocklists.
15. `play_game_sessions` — Authoritative game sessions, state machine, and match scores.
16. `play_game_participants` — Match participants, roles, joined timestamps, and final rankings.
17. `game_invitations` — Time-limited duel challenges with status tracking (PENDING, ACCEPTED, REJECTED, EXPIRED).
18. `duel_quota_usage` — Immutable ledger of dual-participant quota consumption with idempotency keys.
19. `game_statistics` — Player gaming statistics, win/loss records, and high-scores.
20. `game_action_events` — Audit trail of timestamped moves and game actions.

---

## 6. Configuration & Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `BOT_TOKEN` | Telegram Bot Token from `@BotFather` | `8301943432:AAFtX...` |
| `BOT_MODE` | Bot execution mode (`polling` or `webhook`) | `polling` |
| `BASE_URL` | Public HTTPS URL for webhook callbacks | `https://likby.onrender.com` |
| `WEBHOOK_SECRET_TOKEN` | Secret header string for Telegram webhook validation | `your_secret_32_hex` |
| `DATABASE_URL` | SQLite or external database connection URL | `sqlite+aiosqlite:///likby.db` |
| `STORAGE_PROVIDER` | Media storage provider (`local` or `r2`) | `local` |
| `R2_ACCOUNT_ID` | Cloudflare Account ID for R2 storage | `your_account_id` |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 S3 Access Key | `your_access_key` |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 S3 Secret Key | `your_secret_key` |
| `R2_BUCKET_NAME` | Cloudflare R2 bucket name | `likby-media` |

---

## 7. Local Development Quickstart

### Prerequisites
* Python 3.11 or newer (Python 3.12 / 3.13 supported)
* Git

### Step-by-Step Setup

```bash
# 1. Clone repository
git clone https://github.com/likby-dev/LikBy.git
cd LikBy

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies in editable mode
pip install -e .

# 4. Configure environment
cp .env.example .env
# Edit .env with your BOT_TOKEN and settings

# 5. Launch bot in local polling mode
python -m likby.main --mode polling
```

---

## 8. Testing & QA Automation

LikBy maintains automated tests covering unit domain logic, repository persistence, API endpoints, and end-to-end service workflows:

```bash
# Run all tests
python -m pytest -v

# Run with coverage report
python -m pytest --cov=likby --cov-report=term-missing
```

### Verified Test Results
```text
============================= 55 passed in 12.53s =============================
tests/integration/test_api.py::test_health_live PASSED
tests/integration/test_api.py::test_root_endpoint PASSED
tests/integration/test_api.py::test_webhook_rejects_missing_or_invalid_secret_token PASSED
tests/integration/test_new_repositories.py::test_message_and_outbox_repositories PASSED
tests/integration/test_new_repositories.py::test_social_and_subscription_repositories PASSED
tests/integration/test_sqlite_repositories.py::test_user_repository_crud PASSED
tests/integration/test_sqlite_repositories.py::test_report_repository PASSED
tests/unit/test_config.py::test_render_host_auto_prefixes_https PASSED
tests/unit/test_transcript.py::test_transcript_formatting_specification PASSED
tests/unit/test_media_archival.py::test_media_archival_and_hash_calculation PASSED
tests/unit/test_karma_service.py::test_session_rating_and_karma_lifecycle PASSED
tests/unit/test_social_service.py::test_mutual_like_friendship_and_capacity_limits PASSED
tests/unit/test_discovery_and_subscriptions.py::test_id_search_daily_quota_and_upgrade PASSED
... (55 total test cases passed with 100% pass rate)
```

---

## 9. Production Deployment Guide (Render)

LikBy is pre-configured for seamless zero-downtime deployment on [Render](https://render.com).

### Option A: Render Blueprint (Recommended — 1-Click Setup)

Render will automatically parse [`render.yaml`](render.yaml) to configure the web service, health checks, ports, and environment variables:

1. Log in to [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** $\to$ **Blueprint**.
3. Connect your GitHub repository (`https://github.com/likby-dev/LikBy`).
4. Render detects `render.yaml`. Enter your `BOT_TOKEN` (from `@BotFather`).
5. Click **Apply**. Render will automatically build, deploy, configure the Telegram Webhook, and launch the service!

### Option B: Manual Web Service Setup

If you prefer manual configuration:

1. Click **New +** $\to$ **Web Service**.
2. Connect your GitHub repository: `https://github.com/likby-dev/LikBy`.
3. Configure the service settings:
   * **Runtime**: `Python 3`
   * **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
   * **Start Command**: `uvicorn likby.main:app --host 0.0.0.0 --port $PORT --workers 1`
   * **Health Check Path**: `/health/live`
4. In the **Environment Variables** tab, add:
   * `PYTHON_VERSION`: `3.11.9`
   * `ENVIRONMENT`: `production`
   * `BOT_MODE`: `webhook`
   * `BOT_TOKEN`: `<your-telegram-bot-token-from-botfather>`
   * `WEBHOOK_SECRET_TOKEN`: `<generate-a-random-32-char-hex-string>`
   * `BASE_URL`: `https://<your-app-name>.onrender.com`
   * `DATABASE_URL`: `sqlite+aiosqlite:///likby.db`
5. Click **Deploy Web Service**.

### Option C: Docker Container Deployment

LikBy includes a production [`Dockerfile`](Dockerfile) and [`.dockerignore`](.dockerignore):
1. In Render, select **Docker** as the runtime.
2. Render builds the container and runs the healthcheck automatically.

### Verifying the Live Deployment

Once deployed, verify your service:
```bash
# 1. Check Root Endpoint
curl -s https://<your-service>.onrender.com/
# Returns: {"app":"LikBy Platform","status":"online","version":"0.1.0",...}

# 2. Check Liveness Probe
curl -i https://<your-service>.onrender.com/health/live
# Returns: HTTP/1.1 200 OK

# 3. Verify Telegram Webhook Registration
curl -s "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
# Confirms url: https://<your-service>.onrender.com/api/v1/telegram/webhook
```

---

## 10. Architecture Documentation Index

For in-depth design specifications and runbooks, consult the `/docs` directory:

| Document | Description |
| :--- | :--- |
| [`05-high-level-architecture.md`](docs/05-high-level-architecture.md) | Layered architecture and subsystem decomposition |
| [`07-domain-model.md`](docs/07-domain-model.md) | Business logic and domain invariants |
| [`11-telegram-bot-design.md`](docs/11-telegram-bot-design.md) | Bot menus, callbacks, and UX flows |
| [`14-matching-engine.md`](docs/14-matching-engine.md) | Compatibility scoring and queue dispatching |
| [`15-chat-session-lifecycle.md`](docs/15-chat-session-lifecycle.md) | Session creation, message relay, and termination |
| [`18-security-threat-model.md`](docs/18-security-threat-model.md) | Threat modeling and authorization controls |
| [`20-storage-and-persistence.md`](docs/20-storage-and-persistence.md) | SQLite schema, indexing, and WAL mode |
| [`28-render-deployment.md`](docs/28-render-deployment.md) | Render hosting specifications and webhooks |
| [`39-architecture-decisions.md`](docs/39-architecture-decisions.md) | Architecture Decision Records (ADRs) |

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
