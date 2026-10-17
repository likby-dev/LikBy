# LikBy Cross-Store Consistency & Outbox Design

---

## 1. The Distributed Data Challenge

Because Supabase (PostgreSQL) and Firebase Firestore do not share a two-phase commit (2PC) protocol, a network fault could occur between updating the match status in PostgreSQL and provisioning the chat session in Firestore.

---

## 2. Outbox & Idempotent Worker Solution

1. **Step 1:** The mutual match is written to PostgreSQL inside an ACID transaction. In the same transaction, a row is inserted into `outbox_events` with status `pending`:
   ```sql
   INSERT INTO outbox_events (event_type, payload, status)
   VALUES ('create_chat_session', '{"match_id": "...", "users": [...]}', 'pending');
   ```
2. **Step 2:** A lightweight background worker reads pending outbox events, calls the Firestore API to create `/chat_sessions/{session_id}`, and updates outbox status to `completed`.
3. **Step 3 (Idempotency):** The Firestore write uses `set()` with deterministic session ID `session_{min_user_id}_{max_user_id}` so repeated attempts produce identical, conflict-free state.
