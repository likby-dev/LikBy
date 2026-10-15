# 12 — API Contracts

## Purpose

Define the internal API between the Telegram adapter and FastAPI backend, and document the future public API for web/Mini App clients.

## Scope

MVP: Internal webhook endpoint. Future: Versioned REST API.

---

## Current API (MVP)

### Webhook Endpoint

```
POST /webhook
```

**Headers:**
- `X-Telegram-Bot-Api-Secret-Token: {webhook_secret}` — Required
- `Content-Type: application/json` — Required

**Body:** Telegram Update JSON object

**Responses:**
- `200 OK` — Update accepted (even if processing fails internally)
- `403 Forbidden` — Invalid secret token

**Note:** Always return `200` to Telegram to prevent retries for application-level errors. Log errors internally.

### Health Endpoints

```
GET /health
```
Returns: `200 OK` with `{"status": "healthy", "timestamp": "..."}`

Used by Render for health monitoring.

```
GET /ready
```
Returns:
- `200 OK` with `{"ready": true}` — Application fully initialized
- `503 Service Unavailable` with `{"ready": false}` — Still starting up

---

## Internal Service API

The Telegram adapter calls application services directly in-process (not via HTTP). These are the service method contracts.

### UserService

```python
class UserService:
    async def get_or_create(self, telegram_id: int) -> UserState
    async def confirm_eligibility(self, user_id: str) -> None
    async def create_profile(self, user_id: str, data: ProfileInput) -> UserProfile
    async def update_profile(self, user_id: str, data: ProfileUpdate) -> UserProfile
    async def get_profile(self, user_id: str) -> UserProfile | None
    async def set_interests(self, user_id: str, interest_ids: list[str]) -> None
    async def complete_onboarding(self, user_id: str) -> None
    async def update_settings(self, user_id: str, data: SettingsUpdate) -> UserSettings
    async def delete_account(self, user_id: str) -> None
```

### MatchingService

```python
class MatchingService:
    async def join_queue(self, user_id: str) -> QueueResult
    async def leave_queue(self, user_id: str) -> None
    async def get_queue_status(self, user_id: str) -> QueueStatus
```

### ChatService

```python
class ChatService:
    async def relay_message(self, sender_id: str, text: str) -> RelayResult
    async def end_session(self, user_id: str, reason: EndReason) -> SessionEndResult
    async def get_active_session(self, user_id: str) -> ChatSession | None
    async def get_partner_telegram_id(self, user_id: str) -> int | None
```

### GameService

```python
class GameService:
    async def invite_game(self, session_id: str, inviter_id: str, game_type: GameType) -> GameInviteResult
    async def accept_game(self, game_id: str, user_id: str) -> GameStartResult
    async def decline_game(self, game_id: str, user_id: str) -> None
    async def submit_move(self, game_id: str, user_id: str, move: GameMove) -> MoveResult
    async def forfeit_game(self, game_id: str, user_id: str) -> None
```

### SafetyService

```python
class SafetyService:
    async def block_user(self, blocker_id: str, blocked_id: str) -> BlockResult
    async def unblock_user(self, blocker_id: str, blocked_id: str) -> None
    async def create_report(self, data: ReportInput) -> Report
    async def check_rate_limit(self, user_id: str, action: str) -> RateLimitResult
```

---

## Future Public API (v1)

### Design: PROPOSED

When the web app or Mini App is built, expose a versioned REST API:

### Base URL

```
/api/v1/
```

### Authentication

| Client | Method |
|---|---|
| Web App | JWT bearer token (login via OAuth/password) |
| Mini App | Telegram `initData` verification → session token |
| Telegram Bot | Internal (in-process) — no HTTP auth needed |

### Common Response Format

```json
{
  "data": { ... },
  "error": null,
  "request_id": "uuid"
}
```

Error response:
```json
{
  "data": null,
  "error": {
    "code": "NOT_FOUND",
    "message": "User not found",
    "details": {}
  },
  "request_id": "uuid"
}
```

### Planned Endpoints (Future)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/profile` | Get current user's profile |
| `PUT` | `/api/v1/profile` | Update profile |
| `GET` | `/api/v1/interests` | List available interests |
| `PUT` | `/api/v1/interests` | Update user interests |
| `GET` | `/api/v1/settings` | Get user settings |
| `PUT` | `/api/v1/settings` | Update settings |
| `POST` | `/api/v1/match/queue` | Join match queue |
| `DELETE` | `/api/v1/match/queue` | Leave match queue |
| `GET` | `/api/v1/session` | Get active session info |
| `POST` | `/api/v1/session/end` | End session |
| `POST` | `/api/v1/block` | Block a user |
| `DELETE` | `/api/v1/block/{user_id}` | Unblock |
| `POST` | `/api/v1/report` | Submit report |
| `POST` | `/api/v1/game/invite` | Invite to game |
| `POST` | `/api/v1/game/{id}/move` | Submit game move |
| `DELETE` | `/api/v1/account` | Delete account |

### Rate Limits (Future API)

| Endpoint Group | Limit |
|---|---|
| Read operations | 60 req/min |
| Match operations | 10 req/min |
| Message relay | 30 req/min |
| Report | 5 req/min |
| Account deletion | 1 req/hour |

### CORS Policy (Future)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tikible.app"],  # Production domain only
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=True,
)
```

---

## Request IDs

Every request gets a unique `request_id` (UUID) for tracing:
- Set in middleware
- Included in all log entries
- Returned in response headers and body
- Used for correlating errors across services

---

## Related Documents

- [Authentication & Authorization](13-authentication-and-authorization.md)
- [High-Level Architecture](05-high-level-architecture.md)
- [Web & Mini App Future](34-web-and-mini-app-future.md)
- [Telegram Bot Design](11-telegram-bot-design.md)
