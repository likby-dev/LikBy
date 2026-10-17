-- ============================================================================
-- LIKBY — SUPABASE POSTGRESQL PRODUCTION RELATIONAL SCHEMA MIGRATION 001
-- Authoritative schema for users, profiles, sessions, friendships, subscriptions,
-- ratings, karma, assets, durable outbox, and multiplayer gaming ecosystem.
-- ============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. USERS & PROFILES
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    unique_id VARCHAR(32) UNIQUE NOT NULL, -- Permanent LikBy unique handle (e.g. @cryptowizard or LK-10001)
    state VARCHAR(32) NOT NULL DEFAULT 'ONBOARDING',
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    age_verified BOOLEAN NOT NULL DEFAULT FALSE,
    terms_accepted_at TIMESTAMPTZ,
    karma_score INTEGER NOT NULL DEFAULT 100,
    report_count INTEGER NOT NULL DEFAULT 0,
    ban_reason TEXT,
    banned_at TIMESTAMPTZ,
    privacy_settings JSONB NOT NULL DEFAULT '{"presence": "active", "allow_search": true}'::jsonb,
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_unique_id_lower ON users(LOWER(unique_id));
CREATE INDEX IF NOT EXISTS idx_users_status_state ON users(status, state);

CREATE TABLE IF NOT EXISTS profiles (
    user_id VARCHAR(64) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    display_name VARCHAR(64) NOT NULL,
    age INTEGER NOT NULL CHECK (age >= 18 AND age <= 120),
    gender VARCHAR(32) NOT NULL,
    bio VARCHAR(500),
    location_country VARCHAR(2), -- ISO 3166-1 alpha-2
    location_city VARCHAR(100),
    languages TEXT[] NOT NULL DEFAULT ARRAY['en']::TEXT[],
    interests JSONB NOT NULL DEFAULT '[]'::JSONB,
    preferred_gender_filter VARCHAR(32)[] NOT NULL DEFAULT ARRAY['ANY']::VARCHAR[],
    min_age_filter INTEGER NOT NULL DEFAULT 18,
    max_age_filter INTEGER NOT NULL DEFAULT 99,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profiles_age_gender ON profiles(age, gender);

-- ============================================================================
-- 2. CHAT SESSION METADATA (Conversation content lives in Firestore)
-- ============================================================================
CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR(64) PRIMARY KEY,
    user_a_id VARCHAR(64) NOT NULL REFERENCES users(id),
    user_b_id VARCHAR(64) NOT NULL REFERENCES users(id),
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    termination_reason VARCHAR(64),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    reported_at TIMESTAMPTZ,
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_chat_sessions_different_users CHECK (user_a_id <> user_b_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_a ON chat_sessions(user_a_id, status);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_b ON chat_sessions(user_b_id, status);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_started_at ON chat_sessions(started_at DESC);

-- ============================================================================
-- 3. LIKES, FRIENDSHIPS & CONNECTION REQUESTS
-- ============================================================================
CREATE TABLE IF NOT EXISTS likes (
    id VARCHAR(64) PRIMARY KEY,
    sender_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(64) REFERENCES chat_sessions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_likes_sender_target UNIQUE (sender_id, target_id),
    CONSTRAINT chk_likes_no_self_like CHECK (sender_id <> target_id)
);

CREATE INDEX IF NOT EXISTS idx_likes_target ON likes(target_id, created_at DESC);

-- Canonical pairwise friendship: user_low_id < user_high_id enforced
CREATE TABLE IF NOT EXISTS friendships (
    id VARCHAR(64) PRIMARY KEY,
    user_low_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_high_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_friendships_pair UNIQUE (user_low_id, user_high_id),
    CONSTRAINT chk_friendships_canonical_ordering CHECK (user_low_id < user_high_id)
);

CREATE INDEX IF NOT EXISTS idx_friendships_user_low ON friendships(user_low_id);
CREATE INDEX IF NOT EXISTS idx_friendships_user_high ON friendships(user_high_id);

CREATE TABLE IF NOT EXISTS connection_requests (
    id VARCHAR(64) PRIMARY KEY,
    requester_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    CONSTRAINT chk_requests_no_self CHECK (requester_id <> target_id)
);

CREATE INDEX IF NOT EXISTS idx_conn_requests_target_status ON connection_requests(target_id, status);
CREATE INDEX IF NOT EXISTS idx_conn_requests_requester ON connection_requests(requester_id, status);

-- ============================================================================
-- 4. SUBSCRIPTIONS & ENTITLEMENTS
-- ============================================================================
CREATE TABLE IF NOT EXISTS subscription_plans (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    tier VARCHAR(32) NOT NULL,
    billing_period VARCHAR(32) NOT NULL,
    price_inr INTEGER NOT NULL,
    price_stars INTEGER NOT NULL DEFAULT 0,
    daily_search_limit INTEGER NOT NULL DEFAULT 3,
    daily_request_limit INTEGER NOT NULL DEFAULT 5,
    max_friends INTEGER NOT NULL DEFAULT 3,
    daily_duel_limit INTEGER NOT NULL DEFAULT 5, -- Base: 5, Spark: 10, Premium: 25, Diamond: -1 (unlimited)
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_subscriptions (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tier VARCHAR(32) NOT NULL DEFAULT 'LIKBY_BASE',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ, -- NULL for base tier
    plan_name VARCHAR(64) NOT NULL DEFAULT 'Base Plan',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_active ON user_subscriptions(user_id, is_active);

CREATE TABLE IF NOT EXISTS daily_usage (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL,
    id_searches_used INTEGER NOT NULL DEFAULT 0,
    connection_requests_used INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_daily_usage_user_date UNIQUE (user_id, usage_date)
);

-- ============================================================================
-- 5. RATINGS, REPUTATION & AUDITABLE KARMA LEDGER
-- ============================================================================
CREATE TABLE IF NOT EXISTS ratings (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    rater_user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rated_user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating_type VARCHAR(16) NOT NULL, -- 'LIKE' (+1) or 'DISLIKE' (-1)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ratings_session_rater UNIQUE (session_id, rater_user_id)
);

CREATE TABLE IF NOT EXISTS karma_ledger (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delta INTEGER NOT NULL,
    reason VARCHAR(64) NOT NULL,
    reference_id VARCHAR(64),
    idempotency_key VARCHAR(128) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_karma_ledger_user ON karma_ledger(user_id, created_at DESC);

-- ============================================================================
-- 6. SAFETY, REPORTS, BLOCKS & AUDIT
-- ============================================================================
CREATE TABLE IF NOT EXISTS reports (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) REFERENCES chat_sessions(id) ON DELETE SET NULL,
    reporter_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reported_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason VARCHAR(64) NOT NULL,
    details TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status, created_at);

CREATE TABLE IF NOT EXISTS moderation_actions (
    id VARCHAR(64) PRIMARY KEY,
    report_id VARCHAR(64) REFERENCES reports(id) ON DELETE SET NULL,
    target_user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type VARCHAR(64) NOT NULL, -- 'WARNING', 'TEMP_BAN', 'PERMANENT_BAN'
    moderator_id VARCHAR(64) NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_blocks (
    id VARCHAR(64) PRIMARY KEY,
    blocker_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_blocks_pair UNIQUE (blocker_id, blocked_id),
    CONSTRAINT chk_blocks_no_self_block CHECK (blocker_id <> blocked_id)
);

CREATE INDEX IF NOT EXISTS idx_user_blocks_blocker ON user_blocks(blocker_id);
CREATE INDEX IF NOT EXISTS idx_user_blocks_blocked ON user_blocks(blocked_id);

CREATE TABLE IF NOT EXISTS audit_events (
    id VARCHAR(64) PRIMARY KEY,
    actor_id VARCHAR(64),
    event_type VARCHAR(64) NOT NULL,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit_events(event_type, created_at DESC);

-- ============================================================================
-- 7. MEDIA ASSETS METADATA (Binary bytes reside in Cloudflare R2)
-- ============================================================================
CREATE TABLE IF NOT EXISTS assets (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id VARCHAR(64) NOT NULL,
    owner_user_id VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    storage_provider VARCHAR(32) NOT NULL DEFAULT 'r2',
    bucket_name VARCHAR(128) NOT NULL DEFAULT 'likby-media',
    object_key VARCHAR(512) UNIQUE NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    original_filename VARCHAR(256),
    telegram_file_id VARCHAR(256),
    upload_status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_assets_session ON assets(session_id);
CREATE INDEX IF NOT EXISTS idx_assets_sha256 ON assets(sha256);

-- ============================================================================
-- 8. DURABLE OUTBOX (Cross-service reliability & transactional dispatch)
-- ============================================================================
CREATE TABLE IF NOT EXISTS outbox_jobs (
    id VARCHAR(64) PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL, -- 'firestore.persist_message', 'r2.archive_media', 'telegram.deliver_message'
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(128) UNIQUE NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    locked_at TIMESTAMPTZ,
    last_error_code VARCHAR(64),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_outbox_jobs_claim ON outbox_jobs(status, next_attempt_at) WHERE status IN ('PENDING', 'FAILED');

-- ============================================================================
-- 9. LIKBY PLAY MULTIPLAYER & SOLO GAMING ECOSYSTEM
-- ============================================================================
CREATE TABLE IF NOT EXISTS play_game_sessions (
    id VARCHAR(64) PRIMARY KEY,
    game_id VARCHAR(64) NOT NULL,
    mode VARCHAR(16) NOT NULL, -- 'DUEL' or 'SOLO'
    status VARCHAR(32) NOT NULL DEFAULT 'CREATED',
    rules_version VARCHAR(16) NOT NULL DEFAULT '1.0',
    game_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_play_sessions_game ON play_game_sessions(game_id, status);

CREATE TABLE IF NOT EXISTS play_game_participants (
    id VARCHAR(64) PRIMARY KEY,
    game_session_id VARCHAR(64) NOT NULL REFERENCES play_game_sessions(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    participant_role VARCHAR(32) NOT NULL DEFAULT 'PLAYER',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    final_score INTEGER NOT NULL DEFAULT 0,
    result_status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    CONSTRAINT uq_participant_session_user UNIQUE (game_session_id, user_id)
);

CREATE TABLE IF NOT EXISTS game_invitations (
    id VARCHAR(64) PRIMARY KEY,
    game_id VARCHAR(64) NOT NULL,
    inviter_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invitee_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    game_session_id VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    responded_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_game_invitations_invitee ON game_invitations(invitee_id, status);

CREATE TABLE IF NOT EXISTS duel_quota_usage (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_session_id VARCHAR(64) NOT NULL,
    subscription_tier_snapshot VARCHAR(32) NOT NULL,
    quota_period_start TIMESTAMPTZ NOT NULL,
    quota_period_end TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    idempotency_key VARCHAR(128) NOT NULL,
    CONSTRAINT uq_duel_quota_user_session UNIQUE (user_id, game_session_id)
);

CREATE INDEX IF NOT EXISTS idx_duel_quota_user_period ON duel_quota_usage(user_id, quota_period_start, quota_period_end);

CREATE TABLE IF NOT EXISTS game_statistics (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id VARCHAR(64) NOT NULL,
    duels_played INTEGER NOT NULL DEFAULT 0,
    duels_won INTEGER NOT NULL DEFAULT 0,
    duels_lost INTEGER NOT NULL DEFAULT 0,
    duels_drawn INTEGER NOT NULL DEFAULT 0,
    solos_played INTEGER NOT NULL DEFAULT 0,
    highest_score INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_game_stats_user_game UNIQUE (user_id, game_id)
);

CREATE TABLE IF NOT EXISTS game_action_events (
    id VARCHAR(64) PRIMARY KEY,
    game_session_id VARCHAR(64) NOT NULL REFERENCES play_game_sessions(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type VARCHAR(64) NOT NULL,
    action_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    sequence_number INTEGER NOT NULL,
    server_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_game_action_seq UNIQUE (game_session_id, sequence_number)
);
