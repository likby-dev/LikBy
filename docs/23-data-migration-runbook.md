# 23 — Data Migration Runbook

## Purpose

Provide a step-by-step operational runbook for migrating Tikible's persistent data from the MVP local SQLite store to the production PostgreSQL (Supabase) database with zero data loss and verifiable consistency.

## Scope

Covers the migration of users, profiles, active tickets, chat session metadata, games, blocks, and reports.

---

## Migration Architecture Overview

```mermaid
sequenceDiagram
    autonumber
    actor Admin as DevOps Engineer
    participant SQLite as Source (SQLite WAL)
    participant Script as Migration CLI (ETL)
    participant Postgres as Target (Supabase PG)
    participant Bot as FastAPI / aiogram App

    Admin->>Bot: Put application into Maintenance Mode
    Note over Bot: Webhook responds 503 Service Unavailable<br/>Active sessions gracefully closed
    Admin->>SQLite: Trigger SQLite VACUUM INTO backup.db
    Admin->>Script: Execute migration validation & sync
    Script->>SQLite: Stream rows in batches (1,000)
    Script->>Script: Validate schema types & constraints
    Script->>Postgres: Bulk insert with transaction boundaries
    Script->>Admin: Emit checksums & reconciliation report
    Admin->>Postgres: Verify foreign keys, counts, and indexes
    Admin->>Bot: Update DATABASE_URL & restart application
    Bot->>Postgres: Health check passes -> Bot online
    Admin->>Admin: Verify Telegram bot live interactions
```

---

## Pre-Migration Checklist

Before initiating the migration:

- [ ] **Target Database Provisioned**: Supabase PostgreSQL instance active with all schema migrations applied via Alembic (`alembic upgrade head`).
- [ ] **Network Connectivity**: Migration runner has direct egress to PostgreSQL (port 5432) with sufficient bandwidth.
- [ ] **Maintenance Window Scheduled**: Broadcast a 15-minute maintenance notification to active users via the bot if possible, or schedule during minimum traffic (03:00 - 04:00 UTC).
- [ ] **Read-Only Lock / Maintenance Mode**: Application configuration flag `MAINTENANCE_MODE=true` prepared.
- [ ] **Disk Space Verification**: Ensure at least 3x the SQLite database size is available on the local migration runner for staging snapshots.

---

## Step 1: Snapshot Source SQLite Database

Do NOT copy the live database file directly while processes are active. Use SQLite's online backup API or `VACUUM INTO`:

```bash
# Connect to SQLite CLI and create a clean frozen snapshot
sqlite3 /data/tikible.db "VACUUM INTO '/backup/tikible_freeze_$(date +%Y%m%d_%H%M%S).db';"

# Verify integrity of snapshot
sqlite3 /backup/tikible_freeze_*.db "PRAGMA integrity_check;"
# Output must be: ok
```

---

## Step 2: The Migration Script (`tools/migrate_sqlite_to_pg.py`)

A deterministic Python script handles type conversions, JSON serialization, and batch insertions:

```python
#!/usr/bin/env python3
"""
tools/migrate_sqlite_to_pg.py
Migrates Tikible data from SQLite to PostgreSQL with data validation.
"""
import asyncio
import json
import sqlite3
import sys
from datetime import datetime
import asyncpg

TABLE_ORDER = [
    "users",
    "profiles",
    "match_tickets",
    "chat_sessions",
    "games",
    "user_blocks",
    "reports",
]

def adapt_timestamp(val):
    if not val:
        return None
    if isinstance(val, str):
        return datetime.fromisoformat(val)
    return val

def adapt_json(val):
    if not val:
        return "{}"
    if isinstance(val, str):
        return val # Already valid JSON string
    return json.dumps(val)

async def migrate_table(sqlite_conn: sqlite3.Connection, pg_pool: asyncpg.Pool, table: str):
    print(f"[*] Migrating table: {table}...")
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT * FROM {table}")
    rows = cursor.fetchall()
    cols = [desc[0] for desc in cursor.description]

    if not rows:
        print(f"    Table {table} is empty. Skipping.")
        return len(rows)

    print(f"    Found {len(rows)} rows to transfer.")

    # Prepare PostgreSQL insert statement
    col_str = ", ".join(cols)
    val_placeholders = ", ".join([f"${i+1}" for i in range(len(cols))])
    query = f"INSERT INTO {table} ({col_str}) VALUES ({val_placeholders}) ON CONFLICT DO NOTHING"

    async with pg_pool.acquire() as pg_conn:
        async with pg_conn.transaction():
            batch_data = []
            for row in rows:
                row_dict = dict(zip(cols, row))
                # Type adjustments
                for k, v in row_dict.items():
                    if k.endswith("_at") and v:
                        row_dict[k] = adapt_timestamp(v)
                    elif k in ("interests", "criteria", "board_state", "match_metadata", "metadata") and v:
                        row_dict[k] = adapt_json(v)
                    elif k in ("languages", "preferred_gender_filter") and isinstance(v, str):
                        try:
                            row_dict[k] = json.loads(v)
                        except Exception:
                            row_dict[k] = [v]
                batch_data.append(tuple(row_dict[c] for c in cols))

            await pg_conn.executemany(query, batch_data)

    print(f"    Completed table: {table}")
    return len(rows)

async def main(sqlite_path: str, pg_dsn: str):
    print(f"--- Starting Tikible Migration ---")
    sqlite_conn = sqlite3.connect(sqlite_path)
    pg_pool = await asyncpg.create_pool(dsn=pg_dsn)

    try:
        total_rows = 0
        for table in TABLE_ORDER:
            count = await migrate_table(sqlite_conn, pg_pool, table)
            total_rows += count
        print(f"[+] Successfully migrated {total_rows} total rows.")
    finally:
        sqlite_conn.close()
        await pg_pool.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python migrate_sqlite_to_pg.py <sqlite_db_path> <postgres_dsn>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
```

---

## Step 3: Verification & Reconciliation

Run the reconciliation checks immediately following script execution:

```sql
-- Run inside target PostgreSQL database
SELECT 
    (SELECT COUNT(*) FROM users) AS pg_user_count,
    (SELECT COUNT(*) FROM profiles) AS pg_profile_count,
    (SELECT COUNT(*) FROM chat_sessions) AS pg_session_count,
    (SELECT COUNT(*) FROM reports) AS pg_report_count;
```

Compare these counts against the source SQLite metrics:
```bash
sqlite3 /backup/tikible_freeze.db "SELECT 'users', count(*) FROM users UNION ALL SELECT 'profiles', count(*) FROM profiles UNION ALL SELECT 'chat_sessions', count(*) FROM chat_sessions UNION ALL SELECT 'reports', count(*) FROM reports;"
```

### Referential Integrity Check

```sql
-- Ensure no orphaned profiles exist
SELECT p.user_id FROM profiles p 
LEFT JOIN users u ON p.user_id = u.id 
WHERE u.id IS NULL;
-- Result MUST be 0 rows
```

---

## Step 4: Cutover & Switchover

1. **Update Production Environment Variables**:
   ```env
   # Change database backend from SQLite to PostgreSQL
   DATABASE_BACKEND=postgres
   DATABASE_URL=postgresql://postgres.xxx:secret@aws-0-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require
   DATABASE_DIRECT_URL=postgresql://postgres:secret@db.xxx.supabase.co:5432/postgres?sslmode=require
   MAINTENANCE_MODE=false
   ```
2. **Deploy / Restart Webhook Worker**: Trigger a redeployment on Render.
3. **Verify Health Check Endpoint**:
   ```bash
   curl -s -f https://api.tikible.com/health | jq .
   # Expected: {"status": "healthy", "database": "connected", "database_backend": "postgres"}
   ```
4. **End-to-End Test**:
   - Send `/start` to the Telegram bot with a test account.
   - Verify profile retrieval and update.
   - Enter matchmaking queue and cancel.

---

## Step 5: Rollback Strategy

If critical failures occur during cutover (e.g., connection pool exhaustion, latency spikes > 2000ms):

1. **Revert Configuration**:
   ```env
   DATABASE_BACKEND=sqlite
   DATABASE_URL=sqlite+aiosqlite:////data/tikible.db
   MAINTENANCE_MODE=false
   ```
2. **Restart Webhook Worker**.
3. **Post-Mortem Log**: Record all timestamps, error codes, and query logs in `incident_reports/` for root cause analysis before re-attempting.
