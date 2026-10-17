# LikBy Backup & Disaster Recovery Architecture

---

## 1. Recovery Objectives
- **Recovery Point Objective (RPO):** < 1 hour for relational data; < 24 hours for media archives.
- **Recovery Time Objective (RTO):** < 30 minutes to restore read/write service from snapshot.

---

## 2. Backup Schedules & Procedures

1. **Supabase PostgreSQL:** Automated daily snapshots managed by Supabase Pro. For local/self-hosted: nightly `pg_dump` compressed and archived to encrypted storage.
2. **SQLite (Development/Staging):** Automated online backup via `VACUUM INTO 'backup/likby_backup_<timestamp>.db'`.
3. **Cloudflare R2:** Versioning enabled on bucket `likby-media-prod` with 30-day lifecycle retention.
