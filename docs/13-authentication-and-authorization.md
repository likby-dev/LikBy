# 13 — Authentication & Authorization

## Purpose

Define how each client authenticates, how authorization is enforced, and what access controls protect user data and operations.

## Scope

Covers Telegram bot auth (MVP), future web/Mini App auth, and internal service authorization rules.

---

## Authentication Channels

### 1. Telegram Webhook (MVP)

| Layer | Mechanism | What It Proves |
|---|---|---|
| **Transport** | `X-Telegram-Bot-Api-Secret-Token` header | Request originates from Telegram (not a spoofed POST) |
| **Identity** | `update.message.from_user.id` (Telegram user ID) | Which Telegram account sent the message |
| **Internal Mapping** | `telegram_id → User.id` lookup | Maps to LikBy internal user |

**Implementation:**

```python
# Webhook endpoint verification
async def webhook_handler(request: Request):
    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not hmac.compare_digest(token or "", settings.WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    # Process update...
```

**What this does NOT prove:**
- It does NOT prove the user's real-world identity
- It does NOT prove the user's age
- It does NOT prove the user controls only one account

### 2. Future: Web Application

| Layer | Mechanism |
|---|---|
| **Transport** | HTTPS |
| **Identity** | JWT bearer token in `Authorization` header |
| **Session** | Server-side session with configurable expiry |

**Decision:** DEFERRED — not implemented in MVP.

### 3. Future: Telegram Mini App

| Layer | Mechanism |
|---|---|
| **Transport** | HTTPS |
| **Identity** | `initData` HMAC verification |
| **Session** | After verification, issue session token |

**Verification algorithm:**
1. Parse `initData` query string
2. Extract `hash` parameter
3. Sort remaining parameters alphabetically
4. Compute HMAC-SHA256 of sorted string using secret derived from bot token
5. Compare computed hash with extracted hash (constant-time)
6. Check `auth_date` for replay protection (max 24h)

**Critical rule:** NEVER trust `initDataUnsafe`. Always verify server-side.

**Decision:** DEFERRED — documented for Phase 9.

---

## Authorization Rules

### Resource Ownership

| Resource | Owner | Access Rule |
|---|---|---|
| User Profile | User | Only the owning user can read/modify |
| Matching Preferences | User | Only the owning user can read/modify |
| Active Session | Both participants | Only participants can send/receive messages |
| Game Session | Both participants | Only participants can submit moves |
| Block | Blocker | Blocker can create/remove; blocked user cannot see it |
| Report | Reporter | Reporter creates; only admins can read/act |

### Operation Authorization Matrix

| Operation | Who Can Do It | Enforcement Point |
|---|---|---|
| View own profile | Authenticated user | UserService checks `user_id` match |
| Edit own profile | Authenticated user | UserService checks `user_id` match |
| Join match queue | Authenticated ACTIVE user | MatchingService checks status |
| Send message in session | Session participant only | ChatService verifies participation |
| End session | Session participant only | ChatService verifies participation |
| Submit game move | Current-turn participant | GameService verifies turn ownership |
| Block user | Session participant | SafetyService verifies active session |
| Report user | Session participant | SafetyService verifies session context |
| Delete account | Account owner | UserService verifies identity |
| View reports | Admin only | Admin check against configured IDs |
| Moderate users | Admin only | Admin check |
| System health | Anyone (no auth) | Public endpoint |

### Admin Authentication

Admins are identified by Telegram user ID configured in environment:

```
ADMIN_TELEGRAM_IDS=123456789,987654321
```

Admin status is checked on every admin command:

```python
def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.ADMIN_TELEGRAM_IDS
```

This is **not** a robust admin system — suitable only for a small team. Future admin panel requires proper authentication.

---

## Session Authorization for Chat

Every message relay and session action requires verifying the caller is a participant:

```python
async def relay_message(self, sender_id: str, text: str) -> RelayResult:
    session = await self._session_repo.get_active_by_user(sender_id)
    if session is None:
        return RelayResult(error="NOT_IN_SESSION")

    # Verify sender is actually a participant
    participants = await self._session_repo.get_participants(session.id)
    if sender_id not in {p.user_id for p in participants}:
        # This should never happen — indicates a bug
        log.error("User not participant in their own session", user_id=sender_id)
        return RelayResult(error="FORBIDDEN")

    partner = next(p for p in participants if p.user_id != sender_id)
    # Relay to partner...
```

### Cross-Session Isolation

| Invariant | Enforcement |
|---|---|
| User A's messages only reach their current partner | Session lookup by `sender_id`; relay to the other participant |
| User cannot read messages from other sessions | No message persistence; relay is point-to-point |
| User cannot join another user's session | Sessions created atomically by matching engine only |

---

## Rate Limiting

### Per-User Limits

| Action | Limit | Window | Enforcement |
|---|---|---|---|
| Messages | 30 | 1 minute | Token bucket in memory |
| Match requests | 10 | 5 minutes | Sliding window |
| Reports | 3 | 1 hour | Sliding window |
| Game moves | 60 | 1 minute | Token bucket |
| Profile updates | 5 | 10 minutes | Sliding window |
| Account deletion | 1 | 1 hour | Cooldown |

### Implementation

Rate limiting is checked in the Telegram middleware layer before reaching services:

```python
class RateLimitMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = extract_user_id(event)
        action = classify_action(event)

        result = await self._safety_service.check_rate_limit(user_id, action)
        if result.exceeded:
            await event.answer("You're doing that too quickly. Please wait.")
            return

        return await handler(event, data)
```

---

## Secret Management

| Secret | Storage | Access |
|---|---|---|
| `BOT_TOKEN` | Environment variable | Bot initialization only |
| `WEBHOOK_SECRET` | Environment variable | Webhook verification only |
| `ADMIN_TELEGRAM_IDS` | Environment variable | Admin check only |
| Future: `JWT_SECRET` | Environment variable | Token signing/verification |
| Future: `DATABASE_URL` | Environment variable | Database connection |
| Future: `AI_API_KEY` | Environment variable | AI provider requests |

**Rules:**
1. Never in source code
2. Never in logs
3. Never in error messages
4. Never in Telegram messages
5. Rotated by regenerating and updating environment variables

---

## Related Documents

- [Security Threat Model](18-security-threat-model.md)
- [API Contracts](12-api-contracts.md)
- [Configuration & Secrets](31-configuration-and-secrets.md)
- [Web & Mini App Future](34-web-and-mini-app-future.md)
