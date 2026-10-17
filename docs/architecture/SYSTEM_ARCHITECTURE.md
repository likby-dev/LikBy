# LikBy System Architecture

**Product:** LikBy (*Meet. Connect. Play.*)  
**Architecture Pattern:** Clean Architecture / Hexagonal Modular Monolith  
**Primary Interface:** Telegram Bot API (via `aiogram 3.x`) & Telegram Mini Apps (`HTML5/Canvas`)  
**Shared Backend:** FastAPI (Python 3.11+)  
**Target Environments:** Local-First (SQLite + Local Disk) & Cloud (Render + Supabase + Firestore + Cloudflare R2)

---

## 1. Architectural Philosophy & Overview

LikBy is designed as a **modular monolith** that balances rapid development, local testability without cloud dependencies, and cost-effective scaling to tens of thousands of daily active users.

```mermaid
graph TD
    User([Telegram User]) <--> TG[Telegram Bot API / Mini App]
    TG <--> |Webhook / Polling| App[FastAPI Application<br/>src/likby/main.py]
    
    subgraph "Core Backend (Modular Monolith)"
        App --> Adapters[Presentation Adapters<br/>Telegram Handlers & REST Routers]
        Adapters --> Services[Application Services<br/>Social, Quotas, Gaming, Payments]
        Services --> Domain[Pure Domain Models<br/>User, Profile, Match, Subscription]
        Services --> Repos[Persistence Interfaces<br/>Repository Pattern]
    end
    
    subgraph "Local-First Storage"
        Repos -.-> |Default Dev| SQLite[(SQLite WAL Database<br/>likby.db)]
        Repos -.-> |Default Dev| LocalDisk[(Local Media Directory<br/>media_store/)]
    end

    subgraph "Target Cloud Storage"
        Repos -.-> |Production| Supabase[(Supabase PostgreSQL<br/>Users, Quotas, Payments)]
        Repos -.-> |Production| Firestore[(Firebase Firestore<br/>Chat Sessions & Transcripts)]
        Repos -.-> |Production| R2[(Cloudflare R2<br/>Content-Addressed Media)]
    end
```

---

## 2. Core Architectural Invariants

1. **Shared Domain Core:** Telegram handlers, Mini Apps, and future web endpoints invoke the exact same application services (`src/likby/services/`). No client possesses private business logic.
2. **Local-First Independence:** The system boots and passes 100% of unit and integration tests using SQLite WAL mode without contacting Supabase, Firestore, or Cloudflare R2.
3. **Explicit Cloud Enforcement:** In `APP_ENV=production`, missing cloud credentials cause a fast-fail exit at boot. The system never silently falls back to ephemeral local storage in production.
4. **Non-Negotiable Persistence:** No self-destructing messages, view-once media, or ephemeral countdown timers. User chat histories and shared media persist until deliberate user deletion.
5. **Strict Content Protection:** All outbound media messages in Telegram use `protect_content=True` to prevent in-app forwarding and saving on supported clients.
6. **Zero-Advertising Guarantee:** Zero ad networks, zero tracking SDKs, zero sponsored chat injections.
