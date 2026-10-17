# LikBy Component Architecture

**Document Version:** 1.0  
**Scope:** Internal module boundaries, layers, and interface contracts

---

## 1. Layered Subsystems

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Integration & Presentation Layer                         │
│    - FastAPI Routers (`src/likby/api/`)                      │
│    - Telegram Handlers, Keyboards, Callbacks (`src/likby/telegram/`)│
│    - Telegram Mini App Static Assets (`src/likby/static/play/`)│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Application & Use Case Layer                             │
│    - Social & Matchmaking (`src/likby/services/social_service.py`)│
│    - Media Quotas (`src/likby/services/media_quota_service.py`)│
│    - Chat Relay (`src/likby/services/chat_relay_service.py`)  │
│    - Subscription Management (`src/likby/services/subscription_service.py`)│
│    - Referral Engine (`src/likby/services/referral_service.py`)│
│    - Server-Authoritative Games (`src/likby/games/`)        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Domain Model Layer (Pure Python)                         │
│    - User, Profile, Subscription, QuotaEvent, Match, Session │
│    - Invariant validations, score calculation                │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Infrastructure & Persistence Layer                       │
│    - Repositories: User, Profile, Subscription, Quota, Match │
│    - SQLite Implementation (`src/likby/repositories/sqlite/`) │
│    - Cloud Adapters: Supabase, Firestore, Cloudflare R2      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Component Responsibilities

### 2.1 Telegram Integration (`src/likby/telegram/`)
- Parses incoming Telegram `Update` objects.
- Manages conversational Finite State Machines (FSM) via `aiogram.fsm`.
- Dispatches formatted responses using reusable keyboard builders.
- Strictly delegates business logic to Application Services.

### 2.2 Media Quota Service (`src/likby/services/media_quota_service.py`)
- Authoritative tracker of daily upload and receipt counts per user.
- Enforces max file size limits (Base: 10MB, Spark: 25MB, Premium: 50MB, Diamond: 100MB).
- Coordinates two-phase reservation and atomic rollback on relay failure.
- Computes daily quota periods aligned to `00:00:00 UTC`.

### 2.3 Games Engine (`src/likby/games/`)
- Implements 17 server-authoritative games (11 Duel Games + 6 Solo Games).
- Enforces turn validation, game board state transitions, KO/win condition checks, and scoring.
- Prevents client-side score forgery and enforces Base tier 5 duel plays/day limit.
