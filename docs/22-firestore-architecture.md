# 22 — Firestore Architecture

## Purpose

Define the alternative document-oriented persistence architecture using Google Cloud Firestore. Document collection topologies, subcollection vs root collection tradeoffs, atomic transaction semantics, indexing constraints, security rules, and evaluate Firestore against LikBy's domain requirements.

## Scope

Covers the technical architecture of a Firestore repository adapter implementing LikBy's repository contracts, and provides a comparative analysis against relational storage.

---

## Evaluation & Decision Context

### Decision: REJECTED as Primary Production Target; Documented as Pluggable Adapter

| Architectural Concern | PostgreSQL / Supabase | Cloud Firestore | Impact on LikBy |
|---|---|---|---|
| **Data Model Fit** | Relational (Foreign keys, joins) | Document / Hierarchical | Social graphs and bidirectional matches fit relational better |
| **Transactional Scope** | Multi-table ACID | Max 500 documents per tx | Matchmaking requires atomic locks across tickets & users |
| **Write Contention** | Row-level locking with timeout | Optimistic lock contention (fail & retry) | High concurrency on queue causes contention failures |
| **Complex Filtering** | GIN indexes, SQL expressions, array intersections | Strict single-inequality, composite index per query pattern | Flexible matchmaking criteria require combinatorial indexes |
| **Cost Model** | Resource-based (RAM/CPU) | Operation-based ($/read, $/write) | High polling/chat session updates scale costs rapidly |
| **Data Sovereignty / Export** | Standard SQL dump (`pg_dump`) | Proprietary export / BigQuery link | Harder compliance with user export / portable deletion |

Firestore is maintained as an architectural option for teams operating within the Google Cloud Platform (GCP) ecosystem or leveraging Firebase Authentication.

---

## Collection Hierarchy & Topology

Firestore organizes data into documents and collections. Two structural models exist:

### Selected Topology: Root Collections with Normalized References

Subcollections (e.g., `users/{userId}/sessions/{sessionId}`) introduce query isolation issues when querying across sessions involving two different users. Therefore, LikBy adopts a **normalized root collection** topology:

```mermaid
graph TD
    subgraph Root Collections
        U[users / {userId}]
        P[profiles / {userId}]
        MT[match_tickets / {ticketId}]
        CS[chat_sessions / {sessionId}]
        G[games / {gameId}]
        UB[user_blocks / {blockId}]
        R[reports / {reportId}]
    end

    U -.->|1:1 ID match| P
    MT -.->|userId| U
    CS -.->|user_a_id, user_b_id| U
    G -.->|sessionId| CS
    UB -.->|blocker_id, blocked_id| U
    R -.->|reporter_id, reported_id| U
```

### Document Schemas

#### 1. `users/{userId}`
```json
{
  "id": "usr_9f8e7d6c",
  "telegram_id": 123456789,
  "state": "ACTIVE",
  "status": "ACTIVE",
  "age_verified": true,
  "terms_accepted_at": "2026-10-15T12:00:00Z",
  "karma_score": 100,
  "report_count": 0,
  "created_at": "2026-10-15T12:00:00Z",
  "updated_at": "2026-10-15T12:00:00Z",
  "last_active_at": "2026-10-15T12:30:00Z"
}
```

#### 2. `profiles/{userId}`
```json
{
  "user_id": "usr_9f8e7d6c",
  "display_name": "Alex",
  "age": 25,
  "gender": "NON_BINARY",
  "bio": "Avid chess player and tech enthusiast.",
  "location_country": "US",
  "location_city": "Seattle",
  "languages": ["en", "es"],
  "interests": ["coding", "gaming", "coffee"],
  "preferred_gender_filter": ["ANY"],
  "min_age_filter": 21,
  "max_age_filter": 35,
  "created_at": "2026-10-15T12:00:00Z",
  "updated_at": "2026-10-15T12:00:00Z"
}
```

#### 3. `match_tickets/{ticketId}`
```json
{
  "id": "tkt_1a2b3c4d",
  "user_id": "usr_9f8e7d6c",
  "status": "WAITING",
  "gender": "NON_BINARY",
  "preferred_genders": ["ANY"],
  "age": 25,
  "min_age": 21,
  "max_age": 35,
  "interests": ["coding", "gaming"],
  "languages": ["en"],
  "created_at": "2026-10-15T12:30:00Z",
  "expires_at": "2026-10-15T12:35:00Z",
  "matched_user_id": null,
  "session_id": null,
  "lock_version": 1
}
```

#### 4. `chat_sessions/{sessionId}`
```json
{
  "id": "ses_5e6f7g8h",
  "user_a_id": "usr_9f8e7d6c",
  "user_b_id": "usr_1a2b3c4d",
  "participants": ["usr_9f8e7d6c", "usr_1a2b3c4d"],
  "status": "ACTIVE",
  "match_score": 0.85,
  "match_metadata": {
    "common_interests": ["gaming"],
    "common_languages": ["en"]
  },
  "message_count": 14,
  "created_at": "2026-10-15T12:31:00Z",
  "last_activity_at": "2026-10-15T12:34:00Z",
  "ended_at": null,
  "ended_by_user_id": null,
  "termination_reason": null
}
```

> [!NOTE]
> The `participants` array field in `chat_sessions` is mandatory to support Firestore `array-contains` queries when querying all active sessions for a given user.

---

## Atomic Matchmaking with Firestore Transactions

Matchmaking requires atomically reading two tickets, verifying compatibility, updating both ticket statuses to `MATCHED`, and creating a new `chat_sessions` document.

```python
# Conceptual implementation in Firestore adapter
from google.cloud import firestore

@firestore.async_transactional
async def execute_match_transaction(
    transaction: firestore.AsyncTransaction,
    db: firestore.AsyncClient,
    ticket_a_ref: firestore.DocumentReference,
    ticket_b_ref: firestore.DocumentReference,
    session_data: dict,
) -> bool:
    # 1. Read both tickets in transaction
    snap_a = await ticket_a_ref.get(transaction=transaction)
    snap_b = await ticket_b_ref.get(transaction=transaction)

    if not snap_a.exists or not snap_b.exists:
        return False

    data_a = snap_a.to_dict()
    data_b = snap_b.to_dict()

    # 2. Concurrency check: verify both are still WAITING
    if data_a.get("status") != "WAITING" or data_b.get("status") != "WAITING":
        return False

    session_id = session_data["id"]
    session_ref = db.collection("chat_sessions").document(session_id)

    # 3. Apply atomic writes
    transaction.update(ticket_a_ref, {
        "status": "MATCHED",
        "matched_user_id": data_b["user_id"],
        "session_id": session_id,
        "matched_at": firestore.SERVER_TIMESTAMP,
    })

    transaction.update(ticket_b_ref, {
        "status": "MATCHED",
        "matched_user_id": data_a["user_id"],
        "session_id": session_id,
        "matched_at": firestore.SERVER_TIMESTAMP,
    })

    transaction.set(session_ref, session_data)
    return True
```

### Contention Mitigation
Under high load, concurrent workers attempting to match the same candidate tickets will trigger `Aborted` exceptions due to optimistic lock contention. Mitigation measures:
- Batch tickets into partitioned queues by language or interest.
- Implement exponential backoff with jitter on retry.
- Cap matchmaking transaction retries at 3 attempts before discarding candidate pair.

---

## Required Composite Indexes (`firestore.indexes.json`)

Firestore requires explicit composite indexes for queries combining multiple fields or equality with range/sort:

```json
{
  "indexes": [
    {
      "collectionGroup": "match_tickets",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "chat_sessions",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "participants", "arrayConfig": "CONTAINS" },
        { "fieldPath": "status", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "reports",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "user_blocks",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "blocker_id", "order": "ASCENDING" },
        { "fieldPath": "blocked_id", "order": "ASCENDING" }
      ]
    }
  ],
  "fieldOverrides": []
}
```

---

## Firestore Security Rules

When accessed via Firebase client SDKs:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    function isAuthenticated() {
      return request.auth != null;
    }

    function isOwner(userId) {
      return isAuthenticated() && request.auth.uid == userId;
    }

    match /users/{userId} {
      allow read: if isAuthenticated();
      allow write: if isOwner(userId);
    }

    match /profiles/{userId} {
      allow read: if isAuthenticated();
      allow write: if isOwner(userId);
    }

    match /match_tickets/{ticketId} {
      allow read, write: if isAuthenticated() && request.auth.uid == resource.data.user_id;
    }

    match /chat_sessions/{sessionId} {
      allow read: if isAuthenticated() && request.auth.uid in resource.data.participants;
      allow write: if false; // Only server backend modifies active chat sessions
    }

    match /reports/{reportId} {
      allow create: if isAuthenticated() && request.auth.uid == request.resource.data.reporter_id;
      allow read, update, delete: if false; // Admin only via backend
    }
  }
}
```

---

## TTL & Data Lifecycle Policies

Firestore supports built-in Time-To-Live (TTL) policies on document timestamp attributes:
- **`match_tickets`**: TTL enabled on `expires_at`. Expired tickets are automatically purged by Google Cloud within 72 hours at no cost.
- **`chat_sessions`**: TTL set to `ended_at + 30 days` to automatically clean up metadata without scheduled cron jobs.
