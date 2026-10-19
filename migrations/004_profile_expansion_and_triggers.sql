-- ============================================================================
-- LIKBY 💜 — SUPABASE POSTGRESQL PRODUCTION MIGRATION 004
-- Profile Expansion (DOB, Location State/Country, Relationship Intent),
-- Server-Side Age Derivation, Universal Automated Timestamp Triggers,
-- Profile Audit Trail, and Performance Indexes.
-- ============================================================================

-- ============================================================================
-- 1. EXPAND PROFILES TABLE SCHEMA
-- ============================================================================
ALTER TABLE profiles
    ADD COLUMN IF NOT EXISTS dob DATE,
    ADD COLUMN IF NOT EXISTS location_state VARCHAR(100),
    ADD COLUMN IF NOT EXISTS relationship_intent VARCHAR(50);

-- Widen location_country to accept full country names or ISO alpha-2 codes
ALTER TABLE profiles
    ALTER COLUMN location_country TYPE VARCHAR(60);

-- ============================================================================
-- 2. UNIVERSAL AUTOMATED TIMESTAMP TRIGGER FUNCTION
-- Automatically keeps updated_at accurate on every row modification.
-- ============================================================================
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger_set_updated_at to all mutable tables
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

-- ============================================================================
-- 3. SERVER-SIDE DOB & AGE SYNCHRONIZATION TRIGGER
-- When dob is provided or updated, automatically calculate and synchronize age.
-- ============================================================================
CREATE OR REPLACE FUNCTION trigger_sync_profile_age()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.dob IS NOT NULL THEN
        -- Calculate exact age based on current date
        NEW.age = EXTRACT(YEAR FROM age(CURRENT_DATE, NEW.dob))::INTEGER;
        -- Validate 18+ requirement
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

-- ============================================================================
-- 4. PROFILE MODIFICATION AUDIT LOGGING TRIGGER
-- Records structured audit log entries in audit_events whenever critical
-- profile attributes change (e.g. display_name, dob, gender, location).
-- ============================================================================
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

-- ============================================================================
-- 5. HIGH-PERFORMANCE SEARCH & FILTERING INDEXES
-- Optimizes geographic search, intent filtering, and language array queries.
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_profiles_location ON profiles (location_country, location_state, location_city);
CREATE INDEX IF NOT EXISTS idx_profiles_relationship_intent ON profiles (relationship_intent);
CREATE INDEX IF NOT EXISTS idx_profiles_dob ON profiles (dob);
CREATE INDEX IF NOT EXISTS idx_profiles_languages ON profiles USING GIN (languages);
CREATE INDEX IF NOT EXISTS idx_profiles_preferred_gender ON profiles USING GIN (preferred_gender_filter);
