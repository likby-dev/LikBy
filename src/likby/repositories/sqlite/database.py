"""
likby.repositories.sqlite.database
SQLite connection initialization, WAL mode configuration, and DDL schema.
"""

from pathlib import Path
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

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    sender_id TEXT NOT NULL,
    sender_display_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'TEXT',
    text TEXT,
    media_asset_id TEXT,
    reply_to_message_id TEXT,
    telegram_message_id INTEGER,
    delivery_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    delivered_at TEXT,
    UNIQUE(session_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_messages_session_seq ON messages(session_id, sequence);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);

-- Media assets table
CREATE TABLE IF NOT EXISTS media_assets (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id TEXT NOT NULL,
    storage_provider TEXT NOT NULL DEFAULT 'r2',
    bucket TEXT NOT NULL,
    object_key TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256_hash TEXT,
    original_filename TEXT,
    telegram_file_id TEXT,
    upload_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    retention_state TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE INDEX IF NOT EXISTS idx_media_session ON media_assets(session_id);

-- Likes table
CREATE TABLE IF NOT EXISTS likes (
    id TEXT PRIMARY KEY,
    sender_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(sender_id, target_id)
);

CREATE INDEX IF NOT EXISTS idx_likes_target ON likes(target_id);

-- Canonical friendships table
CREATE TABLE IF NOT EXISTS friendships (
    id TEXT PRIMARY KEY,
    user_a_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_b_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    source TEXT NOT NULL DEFAULT 'MUTUAL_LIKE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_a_id, user_b_id)
);

CREATE INDEX IF NOT EXISTS idx_friendships_user_a ON friendships(user_a_id);
CREATE INDEX IF NOT EXISTS idx_friendships_user_b ON friendships(user_b_id);

-- Connection requests table
CREATE TABLE IF NOT EXISTS connection_requests (
    id TEXT PRIMARY KEY,
    sender_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_requests_target ON connection_requests(target_id, status);

-- Session ratings table
CREATE TABLE IF NOT EXISTS session_ratings (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    rater_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ratee_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(session_id, rater_id)
);

-- Karma ledger table
CREATE TABLE IF NOT EXISTS karma_ledger (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    reference_id TEXT,
    delta INTEGER NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_karma_user ON karma_ledger(user_id);

-- Subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    tier TEXT NOT NULL DEFAULT 'FREE',
    max_friends INTEGER NOT NULL DEFAULT 3,
    daily_searches_limit INTEGER NOT NULL DEFAULT 3,
    daily_requests_limit INTEGER NOT NULL DEFAULT 5,
    starts_at TEXT NOT NULL,
    expires_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

-- Daily usage table
CREATE TABLE IF NOT EXISTS daily_usage (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_date TEXT NOT NULL,
    searches_count INTEGER NOT NULL DEFAULT 0,
    requests_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(user_id, usage_date)
);

-- Outbox jobs table
CREATE TABLE IF NOT EXISTS outbox_jobs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id TEXT NOT NULL,
    recipient_tg_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    last_error TEXT,
    next_attempt_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_outbox_status_next ON outbox_jobs(status, next_attempt_at);
"""


async def init_sqlite_db(db_path: str) -> aiosqlite.Connection:
    """Connect to SQLite and enforce WAL mode, busy timeout, and schema."""
    clean_path = db_path
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///", "sqlite://"):
        if clean_path.startswith(prefix):
            clean_path = clean_path[len(prefix):]
    db_file = Path(clean_path)
    if db_file.parent and str(db_file.parent) not in ("", "."):
        db_file.parent.mkdir(parents=True, exist_ok=True)
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
