# LikBy Production Migration Plan

**Document Version:** 1.0  
**Target Environment:** Render + Supabase PostgreSQL + Firebase Firestore + Cloudflare R2  

---

## 1. Migration Phasing & Overview

```
Phase 1: Local SQLite & Local Filesystem (Current Verified State)
                           │
                           ▼
Phase 2: Staging on Supabase PostgreSQL & Firebase Emulators
                           │
                           ▼
Phase 3: Production Cutover with Zero Downtime Dual-Write Verification
```

---

## 2. Step-by-Step Production Cutover Procedure

### Step 2.1: Supabase Database Provisioning
1. Create a Supabase project in the target region (e.g., `ap-south-1` for Indian subcontinent / Singapore for Asia-wide).
2. Execute relational migrations in sequence via Supabase SQL Editor or CLI:
   ```bash
   supabase db push migrations/001_supabase_schema.sql
   supabase db push migrations/002_rls_policies.sql
   supabase db push migrations/003_media_quotas_and_protection.sql
   ```
3. Verify table constraints, foreign keys, and RLS policies.

### Step 2.2: Firebase Firestore Configuration
1. Deploy Firestore security rules and index definitions:
   ```bash
   firebase deploy --only firestore:rules,firestore:indexes
   ```
2. Confirm the service account JSON is generated and added to Render environment secrets as `FIREBASE_CREDENTIALS_JSON`.

### Step 2.3: Cloudflare R2 Bucket Provisioning
1. Create bucket `likby-media-prod`.
2. Generate S3-compatible API credentials (Access Key ID and Secret Access Key).
3. Set CORS policies to permit authorized backend media upload and delivery.

### Step 2.4: Render Web Service Configuration
1. Deploy via `render.yaml` with the following production environment variables:
   - `APP_ENV=production`
   - `STORAGE_BACKEND=supabase`
   - `MEDIA_STORAGE_BACKEND=cloudflare_r2`
   - `TELEGRAM_MODE=webhook`
   - `PUBLIC_BASE_URL=https://api.likby.com`
   - `TELEGRAM_WEBHOOK_SECRET=<high-entropy-random-string>`
2. Verify startup logs for successful health check: `GET /health/ready` returns `200 OK`.

---

## 3. Rollback & Disaster Recovery Strategy

- **Relational Rollback:** If Supabase fails during deployment, restore from latest point-in-time recovery (PITR) snapshot or re-route traffic to standby read-replica.
- **Webhook Rollback:** If the webhook endpoint encounters unexpected errors, switch `TELEGRAM_MODE=polling` in staging to drain queued updates while investigating logs.
