# LikBy Database Security Architecture

---

## 1. Supabase PostgreSQL Hardening
- Connection strings use SSL mode `require`.
- RLS enabled across all user, profile, subscription, and social tables (`migrations/002_rls_policies.sql`).
- Direct client access is disabled; only authorized service-role or verified backend roles can query tables.

## 2. SQLite Hardening
- Private directory permissions (`chmod 700 .data/`).
- Database file excluded from git repository (`.gitignore`).
