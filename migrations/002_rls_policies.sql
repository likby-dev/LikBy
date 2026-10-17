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
