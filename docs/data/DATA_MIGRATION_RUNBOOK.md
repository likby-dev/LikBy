# LikBy SQLite to Supabase Data Migration Runbook

---

## 1. Pre-Migration Checklist
- [ ] Take an offline backup snapshot of `likby.db`.
- [ ] Verify Supabase project is active and schema migrations (`001`, `002`, `003`) are applied.
- [ ] Ensure application traffic is temporarily paused or in read-only maintenance mode.

---

## 2. Migration Execution Steps

```bash
# 1. Export SQLite tables to sanitized CSV/JSON
python scripts/maintenance/export_sqlite_data.py --db-path likby.db --out-dir .data/exports/

# 2. Run ETL validation script
python scripts/maintenance/validate_etl_payload.py --dir .data/exports/

# 3. Ingest into Supabase PostgreSQL
python scripts/maintenance/import_supabase_data.py --supabase-url $SUPABASE_URL --key $SUPABASE_SERVICE_ROLE_KEY --dir .data/exports/

# 4. Run integrity checks (row counts, foreign key sanity)
python scripts/maintenance/verify_migration_parity.py
```
