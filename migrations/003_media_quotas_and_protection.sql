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
