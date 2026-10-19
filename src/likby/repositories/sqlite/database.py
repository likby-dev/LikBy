"""
likby.repositories.sqlite.database
SQLite connection initialization, WAL mode configuration, and DDL schema.
"""

from datetime import datetime, timezone
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
    dob TEXT,
    age INTEGER NOT NULL,
    gender TEXT NOT NULL,
    bio TEXT,
    location_country TEXT,
    location_state TEXT,
    location_city TEXT,
    relationship_intent TEXT,
    languages TEXT NOT NULL DEFAULT '["en"]',
    interests TEXT NOT NULL DEFAULT '[]',
    preferred_gender_filter TEXT NOT NULL DEFAULT '["ANY"]',
    min_age_filter INTEGER NOT NULL DEFAULT 18,
    max_age_filter INTEGER NOT NULL DEFAULT 99,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_profiles_location ON profiles (location_country, location_state, location_city);
CREATE INDEX IF NOT EXISTS idx_profiles_intent ON profiles (relationship_intent);
CREATE INDEX IF NOT EXISTS idx_profiles_dob ON profiles (dob);

-- Automated Timestamp Maintenance Triggers
CREATE TRIGGER IF NOT EXISTS trg_profiles_updated_at AFTER UPDATE ON profiles
WHEN (NEW.updated_at IS OLD.updated_at)
BEGIN
    UPDATE profiles SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE user_id = NEW.user_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_users_updated_at AFTER UPDATE ON users
WHEN (NEW.updated_at IS OLD.updated_at)
BEGIN
    UPDATE users SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;


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

-- Session events table
CREATE TABLE IF NOT EXISTS session_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    display_text TEXT NOT NULL,
    sequence INTEGER,
    actor_user_id TEXT,
    details TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_events_session ON session_events(session_id, sequence);

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
    is_active INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'FREE',
    source_transaction_id TEXT
);

-- Daily usage table
CREATE TABLE IF NOT EXISTS daily_usage (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_date TEXT NOT NULL,
    searches_count INTEGER NOT NULL DEFAULT 0,
    requests_count INTEGER NOT NULL DEFAULT 0,
    uploads_count INTEGER NOT NULL DEFAULT 0,
    received_count INTEGER NOT NULL DEFAULT 0,
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

-- Subscription plans table
CREATE TABLE IF NOT EXISTS subscription_plans (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    entitlements_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Provider prices table
CREATE TABLE IF NOT EXISTS provider_prices (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES subscription_plans(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    provider_product_id TEXT,
    amount_minor_units INTEGER NOT NULL,
    currency TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    environment TEXT NOT NULL DEFAULT 'production',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_provider_prices_lookup ON provider_prices(plan_id, provider, active);

-- Payment orders table
CREATE TABLE IF NOT EXISTS payment_orders (
    id TEXT PRIMARY KEY,
    internal_order_id TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_order_id TEXT,
    amount_minor_units INTEGER NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CREATED',
    idempotency_key TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_payment_orders_user ON payment_orders(user_id, status);
CREATE INDEX IF NOT EXISTS idx_payment_orders_provider_order ON payment_orders(provider, provider_order_id);

-- Payment transactions table
CREATE TABLE IF NOT EXISTS payment_transactions (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES payment_orders(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    provider_payment_id TEXT UNIQUE NOT NULL,
    provider_order_id TEXT,
    provider_signature_verified INTEGER NOT NULL DEFAULT 1,
    amount_minor_units INTEGER NOT NULL,
    currency TEXT NOT NULL,
    payment_status TEXT NOT NULL DEFAULT 'CAPTURED',
    captured_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payment_transactions_order ON payment_transactions(order_id);

-- Subscription entitlements table (extended multi-tier)
CREATE TABLE IF NOT EXISTS subscription_entitlements (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'BASE',
    source TEXT NOT NULL DEFAULT 'FREE',
    source_transaction_id TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    starts_at TEXT NOT NULL,
    expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sub_entitlements_user ON subscription_entitlements(user_id, status);

-- Usage counters table
CREATE TABLE IF NOT EXISTS usage_counters (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feature_key TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(user_id, feature_key, period_start)
);

CREATE INDEX IF NOT EXISTS idx_usage_counters_lookup ON usage_counters(user_id, feature_key, period_start);

-- Webhook event ledger
CREATE TABLE IF NOT EXISTS webhook_event_ledger (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_event_id TEXT,
    event_type TEXT NOT NULL,
    signature_verified INTEGER NOT NULL DEFAULT 1,
    processing_status TEXT NOT NULL DEFAULT 'PROCESSED',
    payload_hash TEXT NOT NULL,
    received_at TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    safe_error_code TEXT,
    UNIQUE(provider, provider_event_id)
);

CREATE INDEX IF NOT EXISTS idx_webhook_ledger_provider ON webhook_event_ledger(provider, event_type);

-- Audit events table
CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_events_lookup ON audit_events(entity_type, entity_id);

-- Referral rewards table
CREATE TABLE IF NOT EXISTS referral_rewards (
    id TEXT PRIMARY KEY,
    referrer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invited_user_id TEXT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    qualification_status TEXT NOT NULL DEFAULT 'PENDING',
    reward_status TEXT NOT NULL DEFAULT 'PENDING',
    reward_entitlement_id TEXT,
    qualified_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_referral_rewards_referrer ON referral_rewards(referrer_user_id, reward_status);

-- LikBy Play Game Sessions table
CREATE TABLE IF NOT EXISTS play_game_sessions (
    id TEXT PRIMARY KEY,
    game_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CREATED',
    rules_version INTEGER NOT NULL DEFAULT 1,
    state_data TEXT NOT NULL DEFAULT '{}',
    current_turn_user_id TEXT,
    round_number INTEGER NOT NULL DEFAULT 1,
    max_rounds INTEGER NOT NULL DEFAULT 1,
    winner_id TEXT,
    result_summary TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    expires_at TEXT,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_play_sessions_status ON play_game_sessions(status);
CREATE INDEX IF NOT EXISTS idx_play_sessions_game ON play_game_sessions(game_id, status);

-- LikBy Play Game Participants table
CREATE TABLE IF NOT EXISTS play_game_participants (
    game_session_id TEXT NOT NULL REFERENCES play_game_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'CHALLENGER',
    joined_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    final_score INTEGER NOT NULL DEFAULT 0,
    is_winner INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (game_session_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_play_participants_user ON play_game_participants(user_id);

-- LikBy Play Game Invitations table
CREATE TABLE IF NOT EXISTS game_invitations (
    id TEXT PRIMARY KEY,
    sender_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipient_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    session_id TEXT REFERENCES play_game_sessions(id) ON DELETE SET NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_game_invitations_recipient ON game_invitations(recipient_id, status);
CREATE INDEX IF NOT EXISTS idx_game_invitations_sender ON game_invitations(sender_id, status);

-- Duel Quota Usage table
CREATE TABLE IF NOT EXISTS duel_quota_usage (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_session_id TEXT NOT NULL,
    subscription_tier_snapshot TEXT NOT NULL,
    quota_period_start TEXT NOT NULL,
    quota_period_end TEXT NOT NULL,
    consumed_at TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    UNIQUE(user_id, game_session_id)
);

CREATE INDEX IF NOT EXISTS idx_duel_quota_user_period ON duel_quota_usage(user_id, quota_period_start);

-- Game Statistics table
CREATE TABLE IF NOT EXISTS game_statistics (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id TEXT NOT NULL,
    games_played INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    draws INTEGER NOT NULL DEFAULT 0,
    high_score INTEGER NOT NULL DEFAULT 0,
    last_played_at TEXT NOT NULL,
    PRIMARY KEY (user_id, game_id)
);

-- Game Action Events table
CREATE TABLE IF NOT EXISTS game_action_events (
    id TEXT PRIMARY KEY,
    game_session_id TEXT NOT NULL REFERENCES play_game_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    action_payload TEXT NOT NULL DEFAULT '{}',
    sequence_num INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_game_action_events_session ON game_action_events(game_session_id, sequence_num);

-- Media Quota Events table
CREATE TABLE IF NOT EXISTS media_quota_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    media_file_id TEXT,
    operation_type TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'RESERVED',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_media_quota_events_user ON media_quota_events(user_id, operation_type, created_at);
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
        if "dob" not in profile_cols:
            await conn.execute("ALTER TABLE profiles ADD COLUMN dob TEXT")
        if "location_state" not in profile_cols:
            await conn.execute("ALTER TABLE profiles ADD COLUMN location_state TEXT")
        if "relationship_intent" not in profile_cols:
            await conn.execute("ALTER TABLE profiles ADD COLUMN relationship_intent TEXT")

    async with conn.execute("PRAGMA table_info(subscriptions)") as cursor:
        sub_cols = [r[1] for r in await cursor.fetchall()]
        if "source" not in sub_cols:
            await conn.execute("ALTER TABLE subscriptions ADD COLUMN source TEXT DEFAULT 'FREE'")
        if "source_transaction_id" not in sub_cols:
            await conn.execute("ALTER TABLE subscriptions ADD COLUMN source_transaction_id TEXT")

    async with conn.execute("PRAGMA table_info(daily_usage)") as cursor:
        usage_cols = [r[1] for r in await cursor.fetchall()]
        if "uploads_count" not in usage_cols:
            await conn.execute("ALTER TABLE daily_usage ADD COLUMN uploads_count INTEGER NOT NULL DEFAULT 0")
        if "received_count" not in usage_cols:
            await conn.execute("ALTER TABLE daily_usage ADD COLUMN received_count INTEGER NOT NULL DEFAULT 0")

    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_unique_id ON users(unique_id)")
    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_unique_id ON profiles(unique_id)")

    # Seed default plans and prices if not populated
    async with conn.execute("SELECT COUNT(*) FROM subscription_plans") as cursor:
        count_row = await cursor.fetchone()
        plan_count = count_row[0] if count_row else 0

    if plan_count == 0:
        now_iso = datetime.now(timezone.utc).isoformat()
        plans_data = [
            ("plan_base", "BASE", "LikBy Base", 1, '{"max_friends": 3, "daily_likes": 25, "daily_searches": 10, "daily_requests": 3, "daily_games": 3, "daily_uploads": 20, "daily_received": 10}', 1, now_iso, now_iso),
            ("plan_spark", "SPARK", "LikBy Spark", 1, '{"max_friends": 5, "daily_likes": 50, "daily_searches": 25, "daily_requests": 5, "daily_games": 10, "daily_uploads": 40, "daily_received": 20, "profile_boosts": 1}', 1, now_iso, now_iso),
            ("plan_premium", "PREMIUM", "LikBy Premium", 1, '{"max_friends": 15, "daily_likes": 100, "daily_searches": 100, "daily_requests": 15, "daily_games": 25, "daily_uploads": 100, "daily_received": 50, "profile_boosts": 2}', 1, now_iso, now_iso),
            ("plan_diamond", "DIAMOND", "LikBy Diamond", 1, '{"max_friends": 50, "daily_likes": 200, "daily_searches": 250, "daily_requests": 30, "daily_games": 50, "daily_uploads": 250, "daily_received": 100, "profile_boosts": 4, "priority_support": true}', 1, now_iso, now_iso),
        ]
        await conn.executemany(
            "INSERT INTO subscription_plans (id, code, display_name, active, entitlements_json, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            plans_data,
        )

        prices_data = [
            # Base (₹0 / 0 Stars)
            ("prc_base_inr", "plan_base", "RAZORPAY", None, 0, "INR", 0, 1, "production", now_iso),
            ("prc_base_stars", "plan_base", "TELEGRAM_STARS", None, 0, "XTR", 0, 1, "production", now_iso),
            # Spark (₹19 / 15 Stars, 24h)
            ("prc_spark_inr", "plan_spark", "RAZORPAY", None, 1900, "INR", 86400, 1, "production", now_iso),
            ("prc_spark_stars", "plan_spark", "TELEGRAM_STARS", None, 15, "XTR", 86400, 1, "production", now_iso),
            # Premium (₹79 / 60 Stars, 30d; ₹199 / 150 Stars, 90d)
            ("prc_prem_inr_30d", "plan_premium", "RAZORPAY", None, 7900, "INR", 2592000, 1, "production", now_iso),
            ("prc_prem_stars_30d", "plan_premium", "TELEGRAM_STARS", None, 60, "XTR", 2592000, 1, "production", now_iso),
            ("prc_prem_inr_90d", "plan_premium", "RAZORPAY", None, 19900, "INR", 7776000, 1, "production", now_iso),
            ("prc_prem_stars_90d", "plan_premium", "TELEGRAM_STARS", None, 150, "XTR", 7776000, 1, "production", now_iso),
            # Diamond (₹149 / 120 Stars, 30d; ₹399 / 300 Stars, 90d)
            ("prc_diam_inr_30d", "plan_diamond", "RAZORPAY", None, 14900, "INR", 2592000, 1, "production", now_iso),
            ("prc_diam_stars_30d", "plan_diamond", "TELEGRAM_STARS", None, 120, "XTR", 2592000, 1, "production", now_iso),
            ("prc_diam_inr_90d", "plan_diamond", "RAZORPAY", None, 39900, "INR", 7776000, 1, "production", now_iso),
            ("prc_diam_stars_90d", "plan_diamond", "TELEGRAM_STARS", None, 300, "XTR", 7776000, 1, "production", now_iso),
        ]
        await conn.executemany(
            "INSERT INTO provider_prices (id, plan_id, provider, provider_product_id, amount_minor_units, currency, duration_seconds, active, environment, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            prices_data,
        )

    await conn.commit()
    return conn
