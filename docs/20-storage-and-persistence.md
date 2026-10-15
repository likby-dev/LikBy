# 20 — Storage & Persistence

## Purpose

Define the storage architecture, SQLite configuration, repository interface design, and deployment persistence constraints.

## Scope

Covers the MVP SQLite implementation and documents the migration path to production databases.

---

## Storage Decision

### Decision: DECIDED — SQLite with WAL mode for MVP

| Factor | SQLite | PostgreSQL (Supabase) | Firestore |
|---|---|---|---|
| Cost | Free | Free tier (limited) | Free tier (limited) |
| Setup complexity | Zero | Account + connection string | Account + credentials |
| Local development | Excellent | Requires running PG or remote | Requires emulator or remote |
| Transactions | Full ACID | Full ACID | Optimistic, may fail under contention |
| Concurrent writes | Single writer | Multi-writer | Multi-writer (with contention) |
| Deployment | File-based (ephemeral on Render free) | Remote (persistent) | Remote (persistent) |
| Migration needed for production | **Yes** | No (is the target) | No (is the target) |

### Why SQLite

1. **Zero cost, zero setup** — no external accounts or services needed to develop and test
2. **Full SQL** — proper transactions, foreign keys, constraints
3. **Repository interfaces** — enable swapping to PostgreSQL without changing domain code
4. **Sufficient for MVP** — single-instance, low-traffic demonstration

### SQLite Limitations (Acknowledged)

1. **Single writer** — only one write transaction at a time (WAL helps with reads)
2. **Ephemeral on Render free tier** — database file lost on restart
3. **No network access** — cannot share between instances
4. **No built-in encryption at rest** — data on disk is readable

---

## SQLite Configuration

```python
# Database initialization
async def init_database(db_path: str) -> aiosqlite.Connection:
    db = await aiosqlite.connect(db_path)

    # Enable WAL mode for better read concurrency
    await db.execute("PRAGMA journal_mode=WAL")

    # Set busy timeout (5 seconds) to retry on lock contention
    await db.execute("PRAGMA busy_timeout=5000")

    # Enable foreign key enforcement
    await db.execute("PRAGMA foreign_keys=ON")

    # Synchronous mode: NORMAL for better performance with WAL
    await db.execute("PRAGMA synchronous=NORMAL")

    await db.commit()
    return db
```

### Write Serialization

To prevent `database is locked` errors under concurrent async operations, use a write serialization lock:

```python
class SQLiteAdapter:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db
        self._write_lock = asyncio.Lock()

    async def execute_write(self, query: str, params: tuple = ()) -> None:
        async with self._write_lock:
            await self._db.execute(query, params)
            await self._db.commit()

    async def execute_write_transaction(self, operations: list[tuple[str, tuple]]) -> None:
        async with self._write_lock:
            await self._db.execute("BEGIN IMMEDIATE")
            try:
                for query, params in operations:
                    await self._db.execute(query, params)
                await self._db.commit()
            except Exception:
                await self._db.rollback()
                raise
```

---

## Schema

### Users

```sql
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    telegram_id INTEGER UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    is_eligible INTEGER NOT NULL DEFAULT 0,
    onboarding_complete INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### User Profiles

```sql
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    bio TEXT DEFAULT '',
    gender TEXT,
    age_range TEXT
);
```

### Matching Preferences

```sql
CREATE TABLE IF NOT EXISTS matching_preferences (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    preferred_gender TEXT,
    preferred_age_range TEXT,
    interests_weight REAL DEFAULT 0.5
);
```

### Interests & User Interests

```sql
CREATE TABLE IF NOT EXISTS interests (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_interests (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    interest_id TEXT NOT NULL REFERENCES interests(id),
    PRIMARY KEY (user_id, interest_id)
);
```

### Queue Entries

```sql
CREATE TABLE IF NOT EXISTS queue_entries (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
```

### Chat Sessions & Participants

```sql
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    ended_at TEXT,
    end_reason TEXT,
    match_reason TEXT
);

CREATE TABLE IF NOT EXISTS session_participants (
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    left_at TEXT,
    PRIMARY KEY (session_id, user_id)
);
```

### Blocks

```sql
CREATE TABLE IF NOT EXISTS blocks (
    id TEXT PRIMARY KEY,
    blocker_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    UNIQUE(blocker_id, blocked_id)
);
```

### Reports

```sql
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    reported_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    session_id TEXT REFERENCES chat_sessions(id) ON DELETE SET NULL,
    category TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
```

### Game Tables

```sql
CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY,
    chat_session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    game_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'invited',
    created_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS game_participants (
    game_id TEXT NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    is_current_turn INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (game_id, user_id)
);

CREATE TABLE IF NOT EXISTS game_states (
    game_id TEXT PRIMARY KEY REFERENCES game_sessions(id) ON DELETE CASCADE,
    board TEXT NOT NULL,
    turn_number INTEGER NOT NULL DEFAULT 0,
    winner_id TEXT,
    is_draw INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS game_actions (
    id TEXT PRIMARY KEY,
    game_id TEXT NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_data TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
```

### User Settings

```sql
CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    notifications_enabled INTEGER NOT NULL DEFAULT 1,
    icebreakers_enabled INTEGER NOT NULL DEFAULT 1
);
```

---

## Schema Migrations

### Decision: DECIDED — Version-tracked DDL scripts

```python
SCHEMA_VERSION = 1

MIGRATIONS = {
    1: [
        "CREATE TABLE IF NOT EXISTS users ...",
        "CREATE TABLE IF NOT EXISTS user_profiles ...",
        # ... all initial tables
    ],
    # Future:
    # 2: ["ALTER TABLE users ADD COLUMN ..."],
}
```

Migration runner checks current version and applies pending migrations:

```python
async def run_migrations(db: aiosqlite.Connection):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        )
    """)
    row = await db.execute("SELECT version FROM schema_version")
    current = (await row.fetchone()) or (0,)
    current_version = current[0]

    for version in sorted(MIGRATIONS.keys()):
        if version > current_version:
            for statement in MIGRATIONS[version]:
                await db.execute(statement)
            await db.execute("INSERT OR REPLACE INTO schema_version VALUES (?)", (version,))
            await db.commit()
```

---

## Deployment Persistence Matrix

| Environment | Storage | Persistence | Data Survives Restart? |
|---|---|---|---|
| Local development | SQLite file | Durable (local disk) | ✅ Yes |
| Render free tier | SQLite file | **Ephemeral** | ❌ **No** — lost on restart/redeploy/sleep |
| Render paid tier + PG | PostgreSQL | Durable (managed) | ✅ Yes |
| Supabase free tier | PostgreSQL | Durable (with pause risk) | ✅ Yes (if not paused) |

> [!WARNING]
> **The Render free tier uses an ephemeral filesystem.** Every restart, redeploy, or sleep cycle destroys the SQLite database. This is acceptable for development and demonstrations only. Production deployment REQUIRES an external database.

---

## Storage Rules Compliance

| Rule | Implementation |
|---|---|
| No conversation history | ✅ MessageEnvelope is in-memory only; never persisted |
| No message content persistence | ✅ No `messages` table; relay-and-discard |
| Minimum data collection | ✅ Only profile, preferences, blocks, reports metadata |
| Explicit retention periods | ✅ 90-day cleanup for sessions, reports |
| No secrets in source | ✅ Environment variables only |
| No secrets in logs | ✅ Redaction filter on structured logging |
| Migrations and versioned schemas | ✅ Version-tracked DDL |

---

## Related Documents

- [Domain Model](07-domain-model.md) — Entity definitions
- [Entity Relationships](08-entity-relationships.md) — Foreign keys and cascades
- [Supabase Architecture](21-supabase-architecture.md) — Future PostgreSQL migration
- [Firestore Architecture](22-firestore-architecture.md) — Future document-store option
- [Render Deployment](28-render-deployment.md) — Deployment constraints
- [Backup & Recovery](32-backup-and-recovery.md) — Data protection
