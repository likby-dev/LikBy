"""
tikible.repositories.sqlite.database
SQLite connection initialization, WAL mode configuration, and DDL schema.
"""

import aiosqlite


SQLITE_SCHEMA_DDL = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    telegram_id INTEGER UNIQUE NOT NULL,
    unique_id TEXT UNIQUE,
    state TEXT NOT NULL DEFAULT 'ONBOARDING_AGE_GATE',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    age_verified INTEGER NOT NULL DEFAULT 0,
    terms_accepted_at TEXT,
    karma_score INTEGER NOT NULL DEFAULT 100,
    report_count INTEGER NOT NULL DEFAULT 0,
    ban_reason TEXT,
    banned_at TEXT,
    last_active_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_state ON users(state);

-- Profiles table
CREATE TABLE IF NOT EXISTS profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    unique_id TEXT UNIQUE,
    display_name TEXT NOT NULL,
    age INTEGER NOT NULL,
    gender TEXT NOT NULL,
    bio TEXT,
    location_country TEXT,
    location_city TEXT,
    languages TEXT NOT NULL DEFAULT '["en"]',
    interests TEXT NOT NULL DEFAULT '[]',
    preferred_gender_filter TEXT NOT NULL DEFAULT '["ANY"]',
    min_age_filter INTEGER NOT NULL DEFAULT 18,
    max_age_filter INTEGER NOT NULL DEFAULT 99,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Match tickets table
CREATE TABLE IF NOT EXISTS match_tickets (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_gender TEXT NOT NULL,
    user_age INTEGER NOT NULL,
    languages TEXT NOT NULL,
    interests TEXT NOT NULL,
    preferred_genders TEXT NOT NULL,
    min_age INTEGER NOT NULL,
    max_age INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'WAITING',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    matched_at TEXT,
    matched_user_id TEXT,
    session_id TEXT,
    lock_version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_match_tickets_status ON match_tickets(status, created_at);
CREATE INDEX IF NOT EXISTS idx_match_tickets_user ON match_tickets(user_id);

-- Chat sessions table (Zero message body storage)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    user_a_id TEXT NOT NULL REFERENCES users(id),
    user_b_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    match_score REAL NOT NULL DEFAULT 0.0,
    match_metadata TEXT NOT NULL DEFAULT '{}',
    message_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL,
    ended_at TEXT,
    ended_by_user_id TEXT,
    termination_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_a ON chat_sessions(user_a_id, status);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_b ON chat_sessions(user_b_id, status);

-- Multiplayer games table
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    game_type TEXT NOT NULL,
    player_x_id TEXT NOT NULL REFERENCES users(id),
    player_o_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'IN_PROGRESS',
    current_turn_user_id TEXT NOT NULL,
    board TEXT NOT NULL,
    winner_id TEXT,
    move_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_games_session ON games(session_id, status);

-- User blocks table
CREATE TABLE IF NOT EXISTS user_blocks (
    id TEXT PRIMARY KEY,
    blocker_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    UNIQUE(blocker_id, blocked_id)
);

CREATE INDEX IF NOT EXISTS idx_blocks_blocker ON user_blocks(blocker_id);
CREATE INDEX IF NOT EXISTS idx_blocks_blocked ON user_blocks(blocked_id);

-- Reports table
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL REFERENCES users(id),
    reported_id TEXT NOT NULL REFERENCES users(id),
    session_id TEXT,
    category TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_snippet TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by TEXT,
    action_taken TEXT
);

CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_reported ON reports(reported_id);
"""


async def init_sqlite_db(db_path: str) -> aiosqlite.Connection:
    """Connect to SQLite and enforce WAL mode, busy timeout, and schema."""
    clean_path = db_path.replace("sqlite+aiosqlite:///", "")
    conn = await aiosqlite.connect(clean_path)
    
    # Enable WAL mode for high read concurrency
    await conn.execute("PRAGMA journal_mode = WAL;")
    # Set busy timeout (5 seconds) to avoid database is locked
    await conn.execute("PRAGMA busy_timeout = 5000;")
    # Enforce foreign key constraints
    await conn.execute("PRAGMA foreign_keys = ON;")
    # Normal synchronous mode optimal for WAL
    await conn.execute("PRAGMA synchronous = NORMAL;")
    
    # Execute DDL
    await conn.executescript(SQLITE_SCHEMA_DDL)

    # Ensure backwards compatibility for existing databases without unique_id column
    async with conn.execute("PRAGMA table_info(users)") as cursor:
        user_cols = [r[1] for r in await cursor.fetchall()]
        if "unique_id" not in user_cols:
            await conn.execute("ALTER TABLE users ADD COLUMN unique_id TEXT")

    async with conn.execute("PRAGMA table_info(profiles)") as cursor:
        profile_cols = [r[1] for r in await cursor.fetchall()]
        if "unique_id" not in profile_cols:
            await conn.execute("ALTER TABLE profiles ADD COLUMN unique_id TEXT")

    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_unique_id ON users(unique_id)")
    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_unique_id ON profiles(unique_id)")

    await conn.commit()
    return conn
