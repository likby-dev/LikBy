# LikBy Firebase Cloud Firestore Schema

---

## 1. Collection Structure

```
/chat_sessions/{session_id}
  ├── session_id: string (UUID)
  ├── participants: [string, string] (user_ids)
  ├── status: "active" | "ended" | "blocked"
  ├── created_at: timestamp
  ├── last_message_at: timestamp
  │
  └── /messages/{message_id}
        ├── message_id: string
        ├── sender_id: string
        ├── message_type: "text" | "photo" | "video" | "voice" | "document"
        ├── content: string (text content or caption)
        ├── media_id: string (optional reference)
        ├── protect_content: boolean (true)
        └── created_at: timestamp
```

---

## 2. Security Rules (`firestore.rules`)

- Read and write access is restricted to verified session participants.
- Deletion is prohibited for individual messages (non-negotiable persistence).
- Session creation requires mutual friendship validation from PostgreSQL.
