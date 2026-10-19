# LikBy Deployment, Health Checks & Rollback Strategy

**Platform:** LikBy  
**Last Updated:** 2026-10-19  
**Deployment Target:** Render Web Service (FastAPI)  

---

## 1. Hosting Architecture & Topology

- **Render Service:** Single FastAPI service running with Uvicorn.
  - Health check path: `/health/live`
  - Readiness check path: `/health/ready`
- **Render Cron:** Optional hourly trigger invoking `/api/v1/cron/maintenance` with `X-Cron-Secret`.
- **Database:** Supabase Managed PostgreSQL (Production) / SQLite WAL (Local Development).
- **Media Storage:** Supabase Storage / Cloudflare R2 with partitioned key structure (`media/{hash[:2]}/{hash[2:4]}/{hash}.{ext}`).

---

## 2. Health & Readiness Verification

### 2.1 `/health/live` (Liveness Probe)
- Returns `{"status": "ok"}` with HTTP 200 immediately.
- Used by orchestrators (Render / Kubernetes) to verify process viability.

### 2.2 `/health/ready` (Readiness Probe)
Performs deep validation across 5 critical subsystems:
1. **Database:** Executes `SELECT 1` with a 2.0s timeout across active connection pools.
2. **Storage:** Confirms R2 or Supabase Storage bucket access and local fallback directories.
3. **Background Workers:** Checks state of `matchmaker_background_worker`, `outbox_background_worker`, and `cron_background_worker`.
4. **Scheduled Maintenance Cron:** Verifies cron telemetry and run count.
5. **Telegram Bot API:** Checks connection to `@LikBy_bot` with smart 300s caching to avoid Telegram rate limits.

---

## 3. Safe Migration Strategy (Expand → Migrate → Contract)

1. **Non-Destructive Schema Evolution:**
   - Relational migrations reside in `migrations/`.
   - All migrations use `IF NOT EXISTS` or safe column addition (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`).
   - Destructive operations (`DROP TABLE`, `DROP COLUMN`) are strictly forbidden without an ADR and a rollback migration script.
2. **Backward-Compatible Entities:**
   - Domain entities provide default values for newly added fields (`dob = None`, `location_state = None`, `relationship_intent = None`).
   - Code running prior versions can coexist with upgraded database schemas during rolling container restarts.

---

## 4. Rollback Plan

If a deployment exhibits regressions:
1. **Fast Container Rollback:** In the Render dashboard, click **Rollback** to revert to the previous verified commit SHA.
2. **Database Backward Compatibility:** Because all schema changes are additive (new columns, new triggers, new indexes), older application versions continue executing queries without syntax errors.
3. **Telegram Webhook Resynchronization:** Invoking `POST /api/v1/telegram/set-webhook` forces registration of the active service URL with Telegram servers.
