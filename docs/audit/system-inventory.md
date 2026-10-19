# LikBy System Inventory & Architectural Map

**Document Status:** Verified against active repository code  
**Timestamp:** 2026-10-19  
**Platform Version:** 0.1.0  

---

## 1. System Overview & Product Positioning

- **Product Name:** `LikBy` (or `LIKBY`).
- **Positioning:** *Meet. Connect. Play.* Privacy-first anonymous social discovery, relationship-building, and gaming ecosystem starting Telegram-first with a shared FastAPI backend.
- **Client Interfaces:**
  1. Telegram Bot (Aiogram 3.x with webhook and long-polling engines).
  2. Telegram Mini App (HTML5 / Vanilla CSS / ES6 JavaScript GameVerse & Chat Companion).
  3. REST & WebSocket APIs for sessions, matchmaking, entitlements, payments, and multiplayer duels.

---

## 2. Technology Stack & Runtime Configuration

| Component | Technology | Role & Responsibility |
|---|---|---|
| **Backend Runtime** | Python 3.11+ (Tested on 3.13) | Asynchronous FastAPI core service |
| **Telegram Bot SDK** | `aiogram` 3.4.0+ | Bot routing, FSM states, Inline Keyboards, Webhook processing |
| **API Framework** | `fastapi` 0.110.0+ / `uvicorn` | REST endpoints, WebSockets, static file serving, lifespan management |
| **Persistence (Relational)** | PostgreSQL (Supabase) / SQLite WAL | Users, profiles, likes, friendships, subscriptions, payments, daily quotas |
| **Persistence (Transcripts)** | Cloud Firestore / Local SQLite | Real-time chat messages, immutable transcripts, session events |
| **Object / Media Storage** | Supabase Storage / Cloudflare R2 | User media (photos, voice, video) with SHA-256 hashed keys and protection |
| **Payment Gateways** | Telegram Stars & Razorpay | Digital goods, passes (`spark`), subscriptions (`premium`, `diamond`) |
| **Mini App Frontend** | Vanilla HTML5 / CSS3 / ES6 | LikBy Play 18-game suite, Web Audio synthesizer, canvas particles |

---

## 3. Entry Points & User Flows

### 3.1 User-Facing Entry Points
1. **Telegram Bot Dispatcher (`/start`, `/menu`, `/chat`, `/profile`, `/play`, `/vip`):**
   - Implemented in `src/likby/telegram/handlers/`.
   - Manages onboarding, date of birth / age verification, gender & matching preference filters, and anonymous chat relay.
2. **Telegram Mini App (`/play`):**
   - Served via FastAPI static mount `src/likby/static/play/index.html`.
   - Launched directly from inline keyboards or Telegram WebApp button.
   - Communicates via REST (`/api/v1/play/*`) and WebSockets (`/api/v1/play/ws/{session_id}`).
3. **HTTP REST Endpoints (`src/likby/api/`):**
   - `/api/v1/payments/*`: Order creation, Razorpay web checkout, webhook ingestion.
   - `/api/v1/play/*`: Game catalogue, daily entitlements, duel invitations, solo puzzle generation, leaderboard, badges, daily riddle.
   - `/api/v1/chat-sessions/*`: Authenticated transcript retrieval, session summaries, message history.
4. **Health & Observability:**
   - `/health/live`: Liveness probe.
   - `/health/ready` & `/ready`: Deep dependency readiness probe (database, storage, workers, bot API).
   - `/metrics`: Prometheus metrics exporter.
   - `/api/v1/cron/maintenance`: Scheduled worker execution for Render cron.

---

## 4. Component & File Map

```
src/likby/
├── api/
│   ├── chat_sessions.py      # Transcripts, session event queries, authorized access
│   ├── payments.py           # Razorpay web orders, signature verification, webhook ingestion
│   └── play.py               # Game catalogue, entitlements, duel lifecycle, WebSockets
├── config.py                 # Pydantic Settings with env parsing and secret protection
├── domain/
│   ├── entities/             # Pure business models (User, Profile, ChatSession, PlayGame, etc.)
│   ├── enums.py              # SubscriptionTier, GameType, FeatureKey, SessionState
│   └── matching/             # Compatibility scoring algorithms (Reciprocal, Age, Languages)
├── games/
│   ├── duel_engines.py       # Server-authoritative logic for 12 turn-based multiplayer duels
│   ├── solo_engines.py       # Logic for 6 solo games
│   └── registry.py           # Registered game catalog (18 games total)
├── main.py                   # FastAPI app, lifespan, background workers, webhook route
├── repositories/
│   ├── interfaces.py         # Abstract repository contracts
│   ├── sqlite/               # SQLite WAL-mode implementations (local dev & tests)
│   └── supabase/             # Supabase PostgreSQL client implementations
├── services/
│   ├── chat_relay_service.py # Anonymous message bridging, content protection, quota gating
│   ├── discovery_service.py  # User search, recommendations, daily search limits
│   ├── media_quota_service.py# Upload and receive daily caps per tier
│   ├── payment_service.py    # Order creation, verification, webhook idempotency
│   ├── play_game_service.py  # Server-authoritative duel validation & state transitions
│   └── subscription_service.py# Authoritative subscription tiers & limits
├── static/play/              # Telegram Mini App client (index.html, styles.css, app.js)
├── telegram/                 # Aiogram bot handlers, keyboards, middlewares, FSM states
└── worker.py                 # Outbox and reconciliation worker runner
```

---

## 5. Data Stores & Ownership

| Data Store | Entities Stored | Authoritative Model |
|---|---|---|
| **Supabase PostgreSQL** | `users`, `profiles`, `likes`, `friendships`, `connection_requests`, `user_subscriptions`, `payment_orders`, `payment_transactions`, `daily_usage`, `game_statistics`, `play_game_sessions`, `outbox_jobs`, `audit_events` | Relational with Foreign Keys, Triggers, and RLS |
| **Local SQLite (Development)** | Identical schema parity with SQLite triggers and PRAGMA checks | Zero cloud credential requirement in local mode |
| **Cloud Firestore** | `chat_sessions/{session_id}/messages` and transcript logs | Append-only document store with real-time listeners |
| **Supabase Storage / R2** | Binary media assets (`media/{hash[:2]}/{hash[2:4]}/{hash}.{ext}`) | Encrypted at rest, signed URL delivery with TTL |

---

## 6. Critical Trust Boundaries

1. **Telegram Webhook (`/api/v1/telegram/webhook`):**
   - Boundary: Public internet to internal bot dispatcher.
   - Verification: `X-Telegram-Bot-Api-Secret-Token` matched against `settings.webhook_secret_token`.
2. **Telegram Mini App (`/api/v1/play/*` & `/api/v1/chat-sessions/*`):**
   - Boundary: Client WebApp to backend API.
   - Verification: Cryptographic HMAC-SHA256 signature verification over `initData` using `bot_token`, with `auth_date` age enforcement.
3. **Payment Provider Webhook (`/api/v1/webhooks/razorpay`):**
   - Boundary: Razorpay cloud to backend API.
   - Verification: HMAC-SHA256 signature over raw request bytes using `razorpay_webhook_secret`. Idempotent ledger to prevent double crediting.
4. **WebSocket Endpoint (`/api/v1/play/ws/{session_id}`):**
   - Boundary: Persistent browser socket to server-side game state.
   - Verification: Session participant authorization required before connection acceptance.
