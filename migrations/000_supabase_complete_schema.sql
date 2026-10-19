-- ============================================================================
-- LIKBY — COMPLETE SUPABASE POSTGRESQL PRODUCTION SETUP SCRIPT
-- Execute this entire script once in Supabase Dashboard -> SQL Editor
-- (https://supabase.com/dashboard/project/deudidrqbyuezltrvrug/sql/new)
-- ============================================================================

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


-- ============================================================================
-- PART 2: ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================
-- ============================================================================
-- LIKBY — SUPABASE POSTGRESQL ROW LEVEL SECURITY (RLS) POLICIES MIGRATION 002
-- Strict least-privilege security policies protecting user privacy and data.
-- ============================================================================

-- Enable Row Level Security on all relational tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE likes ENABLE ROW LEVEL SECURITY;
ALTER TABLE friendships ENABLE ROW LEVEL SECURITY;
ALTER TABLE connection_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE ratings ENABLE ROW LEVEL SECURITY;
ALTER TABLE karma_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE moderation_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE play_game_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE play_game_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE duel_quota_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_statistics ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_action_events ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- 1. Service Role Full Access Bypass (Backend processes execute as service_role)
-- ----------------------------------------------------------------------------
CREATE POLICY service_role_all_users ON users FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_profiles ON profiles FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_sessions ON chat_sessions FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_likes ON likes FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_friendships ON friendships FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_requests ON connection_requests FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_plans ON subscription_plans FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_subscriptions ON user_subscriptions FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_usage ON daily_usage FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_ratings ON ratings FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_karma ON karma_ledger FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_reports ON reports FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_moderation ON moderation_actions FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_blocks ON user_blocks FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_audit ON audit_events FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_assets ON assets FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_outbox ON outbox_jobs FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_play_sessions ON play_game_sessions FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_play_participants ON play_game_participants FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_invitations ON game_invitations FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_duel_quota ON duel_quota_usage FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_game_stats ON game_statistics FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_all_game_actions ON game_action_events FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ----------------------------------------------------------------------------
-- 2. Authenticated End-User Policies (Restricted to Owned / Associated Rows)
-- ----------------------------------------------------------------------------
-- Users can only read active non-banned public profile data or their own row
CREATE POLICY users_select_own ON users FOR SELECT TO authenticated
    USING (id = auth.uid()::text);

-- Profiles: Users can edit their own profile
CREATE POLICY profiles_manage_own ON profiles FOR ALL TO authenticated
    USING (user_id = auth.uid()::text) WITH CHECK (user_id = auth.uid()::text);

-- Chat sessions: only participants can view their session metadata
CREATE POLICY sessions_select_participants ON chat_sessions FOR SELECT TO authenticated
    USING (user_a_id = auth.uid()::text OR user_b_id = auth.uid()::text);

-- Friendships: users can only view their own friendships
CREATE POLICY friendships_select_own ON friendships FOR SELECT TO authenticated
    USING (user_low_id = auth.uid()::text OR user_high_id = auth.uid()::text);

-- Media Assets: only session participants can select asset records
CREATE POLICY assets_select_participants ON assets FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM chat_sessions cs
            WHERE cs.id = assets.session_id
            AND (cs.user_a_id = auth.uid()::text OR cs.user_b_id = auth.uid()::text)
        )
    );

-- Subscription plans: public read for all active plans
CREATE POLICY subscription_plans_read_active ON subscription_plans FOR SELECT TO authenticated
    USING (is_active = true);

-- User subscriptions: read own subscription state
CREATE POLICY subscriptions_select_own ON user_subscriptions FOR SELECT TO authenticated
    USING (user_id = auth.uid()::text);

-- Duel gaming: participants can view their active sessions
CREATE POLICY play_sessions_select_participants ON play_game_sessions FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM play_game_participants p
            WHERE p.game_session_id = play_game_sessions.id
            AND p.user_id = auth.uid()::text
        )
    );


-- ============================================================================
-- PART 3: DAILY MEDIA QUOTAS & PROTECTION
-- ============================================================================
-- ============================================================================
-- LIKBY 💜 — SUPABASE POSTGRESQL MIGRATION 003
-- Daily Media Quotas (Upload & Receive), Concurrency-Safe Ledger,
-- Media Protection Metadata & Non-Destructive Retention Policies.
-- ============================================================================

-- 1. Extend subscription_plans with authoritative daily media quotas & size caps
ALTER TABLE subscription_plans
    ADD COLUMN IF NOT EXISTS daily_upload_limit INTEGER NOT NULL DEFAULT 20,
    ADD COLUMN IF NOT EXISTS daily_receive_limit INTEGER NOT NULL DEFAULT 10,
    ADD COLUMN IF NOT EXISTS max_image_size_bytes BIGINT NOT NULL DEFAULT 20971520, -- 20 MB
    ADD COLUMN IF NOT EXISTS max_video_size_bytes BIGINT NOT NULL DEFAULT 20971520, -- 20 MB
    ADD COLUMN IF NOT EXISTS allowed_media_types TEXT[] NOT NULL DEFAULT ARRAY['PHOTO', 'VIDEO', 'VOICE', 'DOCUMENT', 'STICKER'];

-- Reconcile / Seed authoritative limits for all 4 subscription tiers
UPDATE subscription_plans
SET
    daily_upload_limit = 20,
    daily_receive_limit = 10,
    max_image_size_bytes = 20971520,
    max_video_size_bytes = 20971520
WHERE UPPER(tier) IN ('BASE', 'LIKBY_BASE');

UPDATE subscription_plans
SET
    daily_upload_limit = 40,
    daily_receive_limit = 20,
    max_image_size_bytes = 20971520,
    max_video_size_bytes = 20971520
WHERE UPPER(tier) IN ('SPARK', 'LIKBY_SPARK');

UPDATE subscription_plans
SET
    daily_upload_limit = 100,
    daily_receive_limit = 50,
    max_image_size_bytes = 52428800, -- 50 MB
    max_video_size_bytes = 52428800
WHERE UPPER(tier) IN ('PREMIUM', 'LIKBY_PREMIUM');

UPDATE subscription_plans
SET
    daily_upload_limit = 250,
    daily_receive_limit = 100,
    max_image_size_bytes = 104857600, -- 100 MB
    max_video_size_bytes = 104857600
WHERE UPPER(tier) IN ('DIAMOND', 'LIKBY_DIAMOND');

-- 2. Extend daily_usage with separate upload and received media counters
ALTER TABLE daily_usage
    ADD COLUMN IF NOT EXISTS uploads_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS received_count INTEGER NOT NULL DEFAULT 0;

-- 3. Idempotent Media Quota Event Ledger for Atomic Reservations & Delivery Tracking
CREATE TABLE IF NOT EXISTS media_quota_events (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    media_file_id VARCHAR(256),
    operation_type VARCHAR(32) NOT NULL, -- 'UPLOAD' or 'RECEIVE'
    idempotency_key VARCHAR(128) UNIQUE NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'RESERVED', -- 'RESERVED', 'COMMITTED', 'ROLLED_BACK'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_media_quota_events_user ON media_quota_events(user_id, operation_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_media_quota_events_idempotency ON media_quota_events(idempotency_key);

-- 4. Enable Row Level Security (RLS) on media_quota_events
ALTER TABLE media_quota_events ENABLE ROW LEVEL SECURITY;

-- Backend / Service Role has unrestricted management
CREATE POLICY service_role_all_media_quota_events ON media_quota_events
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- Authenticated users can view their own quota events audit trail
CREATE POLICY media_quota_events_select_own ON media_quota_events
    FOR SELECT TO authenticated
    USING (user_id = auth.uid()::text);

-- ============================================================================
-- LIKBY 💜 — SUPABASE POSTGRESQL PRODUCTION MIGRATION 004
-- Profile Expansion (DOB, Location State/Country, Relationship Intent),
-- Server-Side Age Derivation, Universal Automated Timestamp Triggers,
-- Profile Audit Trail, and Performance Indexes.
-- ============================================================================

-- 1. EXPAND PROFILES TABLE SCHEMA
ALTER TABLE profiles
    ADD COLUMN IF NOT EXISTS dob DATE,
    ADD COLUMN IF NOT EXISTS location_state VARCHAR(100),
    ADD COLUMN IF NOT EXISTS relationship_intent VARCHAR(50);

ALTER TABLE profiles
    ALTER COLUMN location_country TYPE VARCHAR(60);

-- 2. UNIVERSAL AUTOMATED TIMESTAMP TRIGGER FUNCTION
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

DROP TRIGGER IF EXISTS trg_profiles_updated_at ON profiles;
CREATE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

DROP TRIGGER IF EXISTS trg_chat_sessions_updated_at ON chat_sessions;
CREATE TRIGGER trg_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

DROP TRIGGER IF EXISTS trg_user_subscriptions_updated_at ON user_subscriptions;
CREATE TRIGGER trg_user_subscriptions_updated_at
    BEFORE UPDATE ON user_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

DROP TRIGGER IF EXISTS trg_daily_usage_updated_at ON daily_usage;
CREATE TRIGGER trg_daily_usage_updated_at
    BEFORE UPDATE ON daily_usage
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

DROP TRIGGER IF EXISTS trg_game_statistics_updated_at ON game_statistics;
CREATE TRIGGER trg_game_statistics_updated_at
    BEFORE UPDATE ON game_statistics
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

DROP TRIGGER IF EXISTS trg_play_game_sessions_updated_at ON play_game_sessions;
CREATE TRIGGER trg_play_game_sessions_updated_at
    BEFORE UPDATE ON play_game_sessions
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

DROP TRIGGER IF EXISTS trg_outbox_jobs_updated_at ON outbox_jobs;
CREATE TRIGGER trg_outbox_jobs_updated_at
    BEFORE UPDATE ON outbox_jobs
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

-- 3. SERVER-SIDE DOB & AGE SYNCHRONIZATION TRIGGER
CREATE OR REPLACE FUNCTION trigger_sync_profile_age()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.dob IS NOT NULL THEN
        NEW.age = EXTRACT(YEAR FROM age(CURRENT_DATE, NEW.dob))::INTEGER;
        IF NEW.age < 18 THEN
            RAISE EXCEPTION 'Age requirement failed: user must be at least 18 years old (calculated %)', NEW.age;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_profiles_age_sync ON profiles;
CREATE TRIGGER trg_profiles_age_sync
    BEFORE INSERT OR UPDATE OF dob ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION trigger_sync_profile_age();

-- 4. PROFILE MODIFICATION AUDIT LOGGING TRIGGER
CREATE OR REPLACE FUNCTION trigger_audit_profile_changes()
RETURNS TRIGGER AS $$
DECLARE
    changes JSONB := '{}'::jsonb;
BEGIN
    IF OLD.display_name IS DISTINCT FROM NEW.display_name THEN
        changes = changes || jsonb_build_object('display_name', jsonb_build_object('old', OLD.display_name, 'new', NEW.display_name));
    END IF;
    IF OLD.dob IS DISTINCT FROM NEW.dob THEN
        changes = changes || jsonb_build_object('dob', jsonb_build_object('old', OLD.dob, 'new', NEW.dob));
    END IF;
    IF OLD.gender IS DISTINCT FROM NEW.gender THEN
        changes = changes || jsonb_build_object('gender', jsonb_build_object('old', OLD.gender, 'new', NEW.gender));
    END IF;
    IF OLD.location_country IS DISTINCT FROM NEW.location_country OR OLD.location_city IS DISTINCT FROM NEW.location_city THEN
        changes = changes || jsonb_build_object('location', jsonb_build_object('old_country', OLD.location_country, 'new_country', NEW.location_country, 'old_city', OLD.location_city, 'new_city', NEW.location_city));
    END IF;
    IF OLD.relationship_intent IS DISTINCT FROM NEW.relationship_intent THEN
        changes = changes || jsonb_build_object('relationship_intent', jsonb_build_object('old', OLD.relationship_intent, 'new', NEW.relationship_intent));
    END IF;

    IF changes <> '{}'::jsonb THEN
        INSERT INTO audit_events (
            id,
            actor_id,
            event_type,
            aggregate_type,
            aggregate_id,
            payload,
            created_at
        ) VALUES (
            'aud_' || substr(md5(random()::text || clock_timestamp()::text), 1, 16),
            NEW.user_id,
            'PROFILE_UPDATED',
            'PROFILE',
            NEW.user_id,
            changes,
            NOW()
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_profiles_audit ON profiles;
CREATE TRIGGER trg_profiles_audit
    AFTER UPDATE ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION trigger_audit_profile_changes();

-- 5. HIGH-PERFORMANCE SEARCH & FILTERING INDEXES
CREATE INDEX IF NOT EXISTS idx_profiles_location ON profiles (location_country, location_state, location_city);
CREATE INDEX IF NOT EXISTS idx_profiles_relationship_intent ON profiles (relationship_intent);
CREATE INDEX IF NOT EXISTS idx_profiles_dob ON profiles (dob);
CREATE INDEX IF NOT EXISTS idx_profiles_languages ON profiles USING GIN (languages);
CREATE INDEX IF NOT EXISTS idx_profiles_preferred_gender ON profiles USING GIN (preferred_gender_filter);


