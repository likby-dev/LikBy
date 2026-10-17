# LikBy Entity Relationship Model

---

## 1. Entity-Relationship Diagram (Relational Core)

```mermaid
erDiagram
    USERS ||--|| PROFILES : has
    USERS ||--o{ SUBSCRIPTIONS : holds
    USERS ||--o{ MEDIA_QUOTA_EVENTS : logs
    USERS ||--o{ REFERRALS : refers
    USERS ||--o{ LIKES : initiates
    USERS ||--o{ MATCHES : participates
    USERS ||--o{ REPORTS : files

    USERS {
        uuid id PK
        bigint telegram_user_id UK
        string likby_id UK
        string status
        timestamp created_at
    }

    PROFILES {
        uuid id PK
        uuid user_id FK
        string display_name
        int age
        string gender
        string target_gender
        string[] languages
        string bio
        string primary_photo_file_id
    }

    SUBSCRIPTIONS {
        uuid id PK
        uuid user_id FK
        string tier
        timestamp start_time
        timestamp expiry_time
        string status
    }

    MEDIA_QUOTA_EVENTS {
        uuid id PK
        uuid user_id FK
        string event_type
        int file_size_bytes
        string quota_date
        timestamp created_at
    }

    MATCHES {
        uuid id PK
        uuid user_a_id FK
        uuid user_b_id FK
        string status
        timestamp created_at
    }
```

---

## 2. Integrity & Constraint Guarantees

1. **Unique Public Identifier:** `likby_id` has a unique index across `users`. Case-insensitive alphanumeric format `[a-z0-9_]{3,24}`.
2. **Deterministic Match Uniqueness:** To prevent duplicate match records under concurrent mutual likes, `user_a_id` is guaranteed to be lexicographically smaller than `user_b_id` (`user_a_id < user_b_id`) with a compound unique constraint on `(user_a_id, user_b_id)`.
3. **Daily Quota Ledger Integrity:** `MEDIA_QUOTA_EVENTS` records atomic reservations with idempotent transaction IDs to prevent double-charging or phantom quota leaks.
