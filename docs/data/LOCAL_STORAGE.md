# LikBy Local Storage Architecture

---

## 1. Zero-Credential Local Development

LikBy is designed to run seamlessly on a developer's workstation without requiring paid cloud accounts, Supabase API keys, Firebase service accounts, or Cloudflare credentials.

### File Layout:
```
.data/ (or project root)
├── likby.db        <- SQLite database with WAL mode enabled
└── media_store/    <- Content-addressed media directory
    ├── 0a/
    │   └── e1/
    │       └── 0ae1f4...jpg
    └── ...
```

---

## 2. SQLite Configuration & Performance

- **Driver:** `aiosqlite` (asynchronous, non-blocking I/O).
- **Journal Mode:** `PRAGMA journal_mode=WAL;` (Write-Ahead Logging for concurrent readers).
- **Foreign Keys:** `PRAGMA foreign_keys=ON;` (Enforces referential integrity).
- **Busy Timeout:** `PRAGMA busy_timeout=5000;` (Prevents immediate database locked errors under concurrency).
