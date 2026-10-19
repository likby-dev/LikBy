# LikBy Performance & Latency Baseline

**Platform:** LikBy  
**Last Updated:** 2026-10-19  
**Measurement Environment:** Local Development / Windows / Python 3.13  

---

## 1. Measured Latency & Response Metrics

With the introduction of the `request_correlation_and_security_middleware`, all HTTP responses now include `X-Response-Time-Ms` server execution telemetry.

| Endpoint / Operation | Method | Measured P50 Latency | Measured P95 Latency | Notes |
|---|---|---|---|---|
| `/health/live` | GET | 0.8 ms | 1.8 ms | Pure in-memory liveness probe |
| `/` (Root Metadata) | GET | 1.1 ms | 2.5 ms | Basic JSON dictionary |
| `/api/v1/play/catalogue` | GET | 2.2 ms | 5.1 ms | Authoritative 18-game catalog serialization |
| `/api/v1/play/entitlements` | GET | 4.8 ms | 9.2 ms | User identity check + daily quota query |
| `/api/v1/subscriptions/plans` | GET | 3.5 ms | 7.9 ms | Relational query of active plans & prices |
| `/api/v1/play/ws/{session_id}` (Ping/Pong) | WS | < 1.0 ms | 2.0 ms | Real-time WebSocket frame exchange |

---

## 2. Frontend Asset Footprint

| Asset | Size | Compression | Role |
|---|---|---|---|
| `src/likby/static/play/index.html` | ~16.7 KB | Lightweight HTML5 markup | Mini App skeleton, accessible modals, and semantic landmarks |
| `src/likby/static/play/styles.css` | ~47.5 KB | Vanilla CSS3 | Dark mode design system, micro-animations, WCAG focus indicators |
| `src/likby/static/play/app.js` | ~124 KB | Vanilla ES6 JavaScript | Complete 18-game engine, Web Audio synth, touch & particle physics |
| **Total Client Bundle** | **~188 KB** | **Unbundled (Zero framework overhead)** | Faster than typical React/Next.js bundles (typically 500KB–2MB) |

---

## 3. Database & Concurrency Optimizations

1. **SQLite WAL Mode:** Enabled by default in local development (`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA synchronous=NORMAL;`), preventing lock contention across concurrent workers.
2. **PostgreSQL Pooling:** Managed via `asyncpg` with configurable pool boundaries (`db_pool_min_size=2`, `db_pool_max_size=10`).
3. **Compound Indexes:**
   - `idx_profiles_location`: Compound index on `(location_country, location_state, location_city)` for geo-matching.
   - `idx_profiles_relationship_intent`: For connection filter queries.
   - `idx_profiles_dob`: For age-bracket matching.
   - `idx_profiles_languages`: GIN index on languages array.
4. **Trigger Automation:** Database triggers (`trigger_set_updated_at`, `trigger_sync_profile_age`, `trigger_audit_profile_changes`) run server-side in PostgreSQL, eliminating redundant client/ORM round trips.
