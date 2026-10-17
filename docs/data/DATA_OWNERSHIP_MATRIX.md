# LikBy Data Ownership Matrix

**Document Version:** 1.0  
**Scope:** Authoritative source of truth assignment across persistence systems

---

## 1. Storage Systems & Core Domains

LikBy separates data ownership cleanly to eliminate split-brain issues and dual-write corruption.

| Data Domain / Entity | Authoritative System (Cloud) | Local Development System | Rationale |
|:---|:---|:---|:---|
| **User Identity & Auth** | Supabase (PostgreSQL) | SQLite WAL (`likby.db`) | Relational integrity, foreign keys, unique handle constraints |
| **User Profiles & Filters** | Supabase (PostgreSQL) | SQLite WAL (`likby.db`) | Complex indexing, structured filtering by age/gender/languages |
| **Social Likes & Matches** | Supabase (PostgreSQL) | SQLite WAL (`likby.db`) | Strict uniqueness constraints `(user_a_id, user_b_id)` |
| **Subscriptions & Quotas** | Supabase (PostgreSQL) | SQLite WAL (`likby.db`) | ACID transactional reservations and audit ledgers |
| **Payment Records & Orders** | Supabase (PostgreSQL) | SQLite WAL (`likby.db`) | Financial reconciliation, immutable payment event history |
| **Chat Sessions & Messages** | Firebase Cloud Firestore | SQLite WAL (`likby.db`) | Realtime listeners, document hierarchy, high-volume append-only stream |
| **Media Metadata & Permissions**| Supabase (PostgreSQL) | SQLite WAL (`likby.db`) | Access control checks, quota accounting, hash mapping |
| **Media Object Binaries** | Cloudflare R2 | Local Filesystem (`media_store/`) | Large binary storage, zero egress costs, CDN distribution |

---

## 2. Invariant Rules of Ownership

1. **PostgreSQL is Relational Truth:** If an inconsistency arises between relational metadata and an external system, PostgreSQL is the canonical source of truth for accounts, friendship statuses, and subscription entitlements.
2. **Firestore Owns Message Stream:** Individual chat message bodies and delivery timestamps live in Firestore documents under `/sessions/{session_id}/messages/{message_id}`. PostgreSQL only stores the high-level session metadata.
3. **Media Bytes Never in Database:** Database rows store only metadata and SHA-256 object keys. Raw media bytes reside strictly in Cloudflare R2 (or local disk in development).
