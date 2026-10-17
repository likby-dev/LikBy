# Runbook: Database Recovery

1. If SQLite database is corrupted, restore from latest `.data/backups/likby_backup_<timestamp>.db`.
2. In Supabase production, invoke point-in-time recovery (PITR) via the Supabase dashboard.
