# LikBy Supabase PostgreSQL Schema Reference

The relational schema is defined across three production migrations in `migrations/`:
- `001_supabase_schema.sql` — Core tables, foreign keys, and indexes.
- `002_rls_policies.sql` — Row Level Security policies.
- `003_media_quotas_and_protection.sql` — Quota event ledgers and tier limits.

---

## 1. Core Tables Summary

1. **`users`:** Core account record, `telegram_user_id`, `likby_id`, status, age verification.
2. **`profiles`:** Public persona, display name, age, gender, target preferences, languages, bio, primary photo file_id.
3. **`subscriptions`:** User plan (`base`, `spark`, `premium`, `diamond`), start timestamp, expiry timestamp.
4. **`media_quota_events`:** Quota transaction ledger (`upload`, `receive`, `reversal`), byte size, quota date.
5. **`matches`:** Unique mutual match records between two users.
6. **`friendships`:** Active friendship connection states.
7. **`blocks` & `reports`:** Safety and moderation records.

---

## 2. Row Level Security (RLS) Principles

- Direct client access from untrusted web browsers is disabled by default.
- All backend services connect via service-role connection strings or authorized JWTs.
- RLS policies ensure that if public client APIs are enabled in future phases, users can only read their own private profile attributes and friends' public cards.
