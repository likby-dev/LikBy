# 38 — Glossary

## Purpose

Provide precise, unambiguous definitions for all domain entities, architectural concepts, security primitives, and platform-specific terminology used throughout the LikBy project.

---

## Domain & Product Terminology

### Age Gate
The mandatory initial interaction requiring a new user to explicitly confirm they are 18 years of age or older before accessing profile creation or matchmaking.

### Anonymous Relay
The core messaging mechanism where user messages received by the Telegram bot are forwarded to the conversation partner without revealing Telegram IDs, phone numbers, usernames, or persistent metadata.

### Chat Session
An active, bidirectional communication channel established between two matched users (`User A` and `User B`). It tracks status, start/end timestamps, and activity metrics, but does **not** store message text.

### Inactivity Reaper
A background task that checks active chat sessions for silence. Warns participants after 4 minutes of inactivity and automatically terminates the session at 5 minutes to release system resources.

### Karma Score
An internal numerical rating (default: 100) that reflects a user's standing and behavior. Decreased by reports, abusive spam, or immediate skips; increased by completed meaningful conversations. Used to prioritize good actors in queue matching.

### Match Score
A normalized float (`0.0` to `1.0`) computed by the matching engine representing the compatibility of two users based on interest overlap, language commonality, and reciprocal age/gender preferences.

### Match Ticket
A temporary stateful object created when a user enters the matchmaking queue. Contains the user's search criteria and expires after 5 minutes if no compatible partner is found.

### User State vs. User Status
- **User State**: The conversational or operational stage of a user within the application flow (e.g., `ONBOARDING`, `MAIN_MENU`, `WAITING_IN_QUEUE`, `IN_CHAT`, `IN_GAME`).
- **User Status**: The administrative account standing (e.g., `ACTIVE`, `QUARANTINED`, `BANNED`, `DELETED`).

---

## Architecture & Technical Terminology

### aiosqlite
An asynchronous Python library that wraps the standard `sqlite3` driver using thread executors, enabling non-blocking database queries within the `asyncio` event loop.

### Clean Architecture
A software architectural style that organizes code into concentric layers (Domain, Application Services, Repositories/Adapters), keeping domain logic decoupled from external frameworks, databases, and third-party APIs.

### Connection Pooling
The practice of maintaining a cache of open database connections (e.g., via `asyncpg` or Supabase `Supavisor`) that can be reused across incoming requests, avoiding the latency of establishing a new connection per query.

### Expand and Contract Pattern
A zero-downtime database migration technique where breaking schema changes are introduced in phases: first expanding with new columns/tables without breaking old code, deploying updated application code, and finally contracting by dropping obsolete schema elements.

### Row Level Security (RLS)
A PostgreSQL security feature that restricts which table rows an authenticated database connection or user can view, insert, update, or delete based on evaluated SQL policy expressions.

### Server-Authoritative State
An architecture for multiplayer games (e.g., Tic-Tac-Toe) where the central server validates all moves, turn sequences, and winning conditions, preventing clients from submitting forged moves or illegal game states.

### WAL (Write-Ahead Logging)
An SQLite journaling mode where changes are written to a separate `-wal` file before being committed to the main database. Allows multiple concurrent readers while a write transaction is in progress.

---

## Telegram Platform Terminology

### aiogram 3.x
A modern, asynchronous Python framework for interfacing with the Telegram Bot API using `asyncio` and Pydantic models.

### Inline Keyboard
A custom keyboard embedded directly below a specific message bubble in the Telegram chat interface. Tapping an inline button sends a `CallbackQuery` update to the bot server rather than posting a text message.

### Reply Keyboard
A custom persistent keyboard that replaces the standard smartphone text entry keyboard at the bottom of the Telegram screen. Tapping a button sends the button's label as a standard user text message.

### Telegram Mini App (TMA)
A full-screen or half-screen Web application (HTML5/React) that runs inside the Telegram client interface, authenticated via signed cryptographic hashes (`initData`).

### Webhook Secret Token
A random cryptographic token configured during `setWebhook` that Telegram includes in the `X-Telegram-Bot-Api-Secret-Token` HTTP header on every outgoing update, allowing the backend to verify that requests originate from Telegram.

---

## Security & Privacy Terminology

### Definition of Done (DoD)
The formal quality criteria that every feature and pull request must satisfy before merging into the main branch (e.g., linting, strict typing, tests passing, zero-persistence privacy verified).

### RPO & RTO
- **RPO (Recovery Point Objective)**: The maximum tolerable age of unrecoverable data following a disaster (e.g., maximum 5 minutes of metadata loss).
- **RTO (Recovery Time Objective)**: The maximum acceptable time duration to restore system operations following an outage (e.g., restored within 15 minutes).

### STRIDE
A threat modeling methodology used to evaluate system risks across six vectors: **S**poofing, **T**ampering, **R**epudiation, **I**nformation Disclosure, **D**enial of Service, and **E**levation of Privilege.

### Zero-Persistence Chat
The foundational privacy guarantee of LikBy: private conversational message text is received into volatile application memory solely to forward to the matched partner, and is immediately discarded without ever being written to a database, log file, or disk storage.
