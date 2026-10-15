# 15 — Chat Session Lifecycle

## Purpose

Define the complete lifecycle of anonymous chat sessions: creation, message relay, termination, and edge cases.

## Scope

Covers the MVP text-only anonymous chat experience.

---

## Session Creation

A session is created atomically by the matching engine when two compatible users are found.

### Preconditions

- Both users are ACTIVE and in the queue
- Neither user has an active session
- Neither user has blocked the other
- Both pass eligibility checks

### Atomic Operations (Single Transaction)

1. Dequeue User A from `queue_entries`
2. Dequeue User B from `queue_entries`
3. Create `ChatSession` with `status=ACTIVE`
4. Create `SessionParticipant` for User A (`PARTICIPANT_A`)
5. Create `SessionParticipant` for User B (`PARTICIPANT_B`)
6. COMMIT

### Post-Creation Notifications

1. Send icebreaker message to both users
2. Inform both: "You're connected with a new partner!"

---

## Message Relay

### Flow

1. User sends text message to bot
2. Bot identifies sender's active session
3. Bot identifies partner from session participants
4. Bot sends message to partner via `bot.send_message(partner_telegram_id, text)`

### Rules

| Rule | Description |
|---|---|
| Text only (MVP) | Photos, stickers, audio → "Only text messages are supported" |
| No persistence | Message content is NEVER written to database or logs |
| Session-scoped | Messages only relay within the active session |
| Rate limited | Max 30 messages/minute per user |
| Safe formatting | User content escaped with `html.quote()` before sending |
| Delivery failure | If partner has blocked bot → end session, notify sender |

### What Is Logged

- Session ID
- Sender user ID (internal)
- Message timestamp
- "Message relayed" (success/failure)
- **NOT logged**: message content, Telegram username, phone number

---

## Session Termination

### Triggers

| Trigger | Initiated By | Side Effects |
|---|---|---|
| `/stop` | User | Session ends; both notified |
| `/next` | User | Session ends; initiator re-queued |
| `/block` | User | Block recorded; session ends; partner told "partner left" |
| Bot blocked | Partner | Session ends; remaining user notified |
| Idle timeout | System (30 min) | Warning sent; session ends after 5 min with no response |
| Admin action | Admin | Session ends; both notified with appropriate message |

### Termination Procedure

1. Set `ChatSession.status = ENDING`
2. Set `left_at` for both `SessionParticipant` records
3. Cancel any active game in the session
4. Set `ChatSession.status = ENDED`
5. Notify both users (with appropriate message based on trigger)
6. If `/next`: enqueue requesting user

### Race Conditions

| Scenario | Handling |
|---|---|
| Both users send `/stop` simultaneously | First to acquire lock wins; second sees "not in session" |
| `/next` while being matched by another user | `BEGIN IMMEDIATE` ensures atomicity; match creation checks session status |
| Message sent during session end | Message delivery may fail; sender sees "not in session" on next action |
| `/block` + partner sends message | Block + end is atomic; message delivery fails gracefully |

---

## Disconnect and Recovery

### Bot Blocked by User

When a user blocks the Telegram bot:
- `bot.send_message()` returns error 403
- Detected on next message relay or notification attempt
- Session ended with `end_reason=PARTNER_LEFT`
- Partner notified: "Your partner is no longer available"

### Network/Server Issues

If the server restarts:
- In-memory state (message envelopes) is lost
- Session records in SQLite indicate ACTIVE sessions that may be stale
- On restart: check for sessions older than the idle timeout and end them
- Users can re-engage by sending any message, which triggers session lookup

### Stale Session Cleanup

Background task runs periodically (every 5 minutes):
```python
async def cleanup_stale_sessions():
    cutoff = datetime.utcnow() - timedelta(minutes=30)
    stale = await session_repo.get_active_older_than(cutoff)
    for session in stale:
        await chat_service.end_session(session.id, reason=EndReason.TIMEOUT)
```

---

## Icebreakers

### Decision: DECIDED — Deterministic for MVP

On session creation, a random icebreaker is selected from a curated list:

```python
ICEBREAKERS = [
    "🎯 If you could learn any skill instantly, what would it be?",
    "🌍 What's the most interesting place you've ever visited?",
    "📚 What's a book or movie that changed how you think?",
    "🎵 What song always puts you in a good mood?",
    "🍽️ What's the best meal you've ever had?",
    "💡 What's something you recently learned that surprised you?",
    "🎮 What's a hobby you'd love to try but haven't yet?",
    "🌟 What's the best advice you've ever received?",
]
```

If shared interests exist, prefer interest-themed icebreakers:
```python
INTEREST_ICEBREAKERS = {
    "music": "🎵 What kind of music are you into right now?",
    "travel": "✈️ Where's the next place on your travel wishlist?",
    "gaming": "🎮 What game are you playing these days?",
    # ...
}
```

**Future (Phase 6):** AI-generated icebreakers based on shared interests, with deterministic fallback.

---

## Related Documents

- [Data Flow](09-data-flow.md) — Message relay and session diagrams
- [State Machines](10-state-machines.md) — Session state transitions
- [Matching Engine](14-matching-engine.md) — Match creation
- [Telegram Bot Design](11-telegram-bot-design.md) — Message formatting
- [Performance & Concurrency](26-performance-and-concurrency.md) — Concurrent session handling
