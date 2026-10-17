# LikBy Chat & Media Sharing Architecture

---

## 1. Non-Negotiable Persistence Commitment

LikBy guarantees that user conversations and shared media do **not** self-destruct.
- No countdown deletion timers.
- No view-once photo mechanics.
- No automated pruning of past chat sessions.
- Data persists until explicit user-directed deletion.

---

## 2. Content Protection Enforcement

All Telegram dispatches containing photos, videos, voice messages, documents, or stickers are transmitted with:
```python
protect_content=True
```
This instructs Telegram clients to:
- Disable the "Forward" button.
- Prevent saving to the user's gallery or local filesystem.
- Block screenshot capture on supported Android and iOS devices.

*Note: In accordance with our security transparency policy, users are reminded that no software can stop an external physical camera pointed at a screen.*
