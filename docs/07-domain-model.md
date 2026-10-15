# 07 — Domain Model

## Purpose

Define all core domain entities, their fields, ownership, lifecycle, privacy classification, and relationships.

## Scope

Covers all entities needed for the MVP Telegram bot and labels future-only entities.

---

## Entity Classification

| Label | Meaning |
|---|---|
| **Persistent** | Stored in database; survives session restart |
| **Ephemeral** | In-memory only; lost on process restart |
| **Derived** | Computed from other data; not stored independently |
| **Optional** | Only created when the related feature is active |
| **Future** | Designed but not implemented in current phase |

---

## Core Entities

### User

| Field | Type | Privacy | Description |
|---|---|---|---|
| `id` | `str` (UUID) | Internal | Opaque internal identifier |
| `telegram_id` | `int` | **Private** | Telegram user ID — never exposed to other users |
| `status` | `UserStatus` enum | Internal | `PENDING`, `ACTIVE`, `SUSPENDED`, `DELETED` |
| `created_at` | `datetime` | Internal | Account creation timestamp |
| `updated_at` | `datetime` | Internal | Last profile update |
| `is_eligible` | `bool` | Internal | Passed age eligibility check |
| `onboarding_complete` | `bool` | Internal | Completed profile setup |

- **Lifecycle**: Persistent
- **Ownership**: System-managed
- **Deletion**: Hard delete with cascade to profile, preferences, sessions, blocks, reports

### UserProfile

| Field | Type | Privacy | Description |
|---|---|---|---|
| `user_id` | `str` (FK) | Internal | References `User.id` |
| `display_name` | `str` | **Shared on reveal only** | User-chosen name (not Telegram username) |
| `bio` | `str` (optional) | **Shared on reveal only** | Short self-description |
| `gender` | `Gender` enum (optional) | **Used for matching only** | `MALE`, `FEMALE`, `OTHER`, `PREFER_NOT_TO_SAY` |
| `age_range` | `AgeRange` enum (optional) | **Used for matching only** | `18_24`, `25_34`, `35_44`, `45_PLUS` |

- **Lifecycle**: Persistent; 1:1 with User
- **Ownership**: User-managed
- **Deletion**: Deleted with User

### MatchingPreferences

| Field | Type | Privacy | Description |
|---|---|---|---|
| `user_id` | `str` (FK) | Internal | References `User.id` |
| `preferred_gender` | `Gender` enum (optional) | Internal | Filter for match candidates |
| `preferred_age_range` | `AgeRange` enum (optional) | Internal | Filter for match candidates |
| `interests_weight` | `float` (0.0–1.0) | Internal | How much to weight shared interests |

- **Lifecycle**: Persistent; 1:1 with User
- **Ownership**: User-managed
- **Deletion**: Deleted with User

### Interest

| Field | Type | Privacy | Description |
|---|---|---|---|
| `id` | `str` | Internal | Interest tag identifier |
| `name` | `str` | Public | Display name (e.g., "Music", "Travel") |
| `category` | `str` | Public | Grouping category |

- **Lifecycle**: Persistent; system-defined catalog
- **Ownership**: System-managed
- **Deletion**: Not deleted; referenced by UserInterest junction

### UserInterest (Junction)

| Field | Type | Privacy | Description |
|---|---|---|---|
| `user_id` | `str` (FK) | Internal | References `User.id` |
| `interest_id` | `str` (FK) | Internal | References `Interest.id` |

- **Lifecycle**: Persistent; many-to-many
- **Deletion**: Deleted with User

### QueueEntry

| Field | Type | Privacy | Description |
|---|---|---|---|
| `user_id` | `str` (FK) | Internal | References `User.id` |
| `joined_at` | `datetime` | Internal | When user entered queue |
| `expires_at` | `datetime` | Internal | Auto-expire if no match found |

- **Lifecycle**: Ephemeral or short-lived persistent
- **Ownership**: System-managed
- **Deletion**: Removed on match, expiry, or user leave

### ChatSession

| Field | Type | Privacy | Description |
|---|---|---|---|
| `id` | `str` (UUID) | Internal | Session identifier |
| `status` | `SessionStatus` enum | Internal | `MATCHING`, `ACTIVE`, `ENDING`, `ENDED` |
| `created_at` | `datetime` | Internal | Match creation time |
| `ended_at` | `datetime` (optional) | Internal | Session end time |
| `end_reason` | `EndReason` enum (optional) | Internal | `USER_NEXT`, `USER_STOP`, `PARTNER_LEFT`, `TIMEOUT`, `BLOCK`, `ADMIN` |
| `match_reason` | `str` (optional) | Internal | Explainable match description |

- **Lifecycle**: Persistent (metadata only; no message content)
- **Ownership**: System-managed
- **Deletion**: Retained for analytics; deleted with user on account deletion

### SessionParticipant

| Field | Type | Privacy | Description |
|---|---|---|---|
| `session_id` | `str` (FK) | Internal | References `ChatSession.id` |
| `user_id` | `str` (FK) | Internal | References `User.id` |
| `role` | `ParticipantRole` enum | Internal | `PARTICIPANT_A`, `PARTICIPANT_B` |
| `joined_at` | `datetime` | Internal | When user joined session |
| `left_at` | `datetime` (optional) | Internal | When user left session |

- **Lifecycle**: Persistent; exactly 2 per ChatSession
- **Deletion**: Deleted with session or user

### MessageEnvelope

| Field | Type | Privacy | Description |
|---|---|---|---|
| `session_id` | `str` | Internal | Active session |
| `sender_id` | `str` | Internal | Sending user (internal ID) |
| `recipient_id` | `str` | Internal | Receiving user (internal ID) |
| `timestamp` | `datetime` | Internal | Relay timestamp |

- **Lifecycle**: **Ephemeral** — used for routing only, NEVER persisted
- **Message content is NEVER stored**
- **Ownership**: System
- **Deletion**: Garbage collected after relay

### Block

| Field | Type | Privacy | Description |
|---|---|---|---|
| `id` | `str` (UUID) | Internal | Block record identifier |
| `blocker_id` | `str` (FK) | Internal | User who blocked |
| `blocked_id` | `str` (FK) | Internal | User who was blocked |
| `created_at` | `datetime` | Internal | When block was created |

- **Lifecycle**: Persistent
- **Ownership**: Blocker user
- **Deletion**: Deleted on unblock or blocker account deletion

### Report

| Field | Type | Privacy | Description |
|---|---|---|---|
| `id` | `str` (UUID) | Internal | Report identifier |
| `reporter_id` | `str` (FK) | Internal | Reporting user |
| `reported_id` | `str` (FK) | Internal | Reported user |
| `session_id` | `str` (FK, optional) | Internal | Session where incident occurred |
| `category` | `ReportCategory` enum | Internal | Harassment, spam, sexual content, minor, impersonation, exploitation, other |
| `description` | `str` (optional) | Internal | User-provided details (may contain sensitive content) |
| `status` | `ReportStatus` enum | Internal | `PENDING`, `REVIEWED`, `ACTIONED`, `DISMISSED` |
| `created_at` | `datetime` | Internal | Report timestamp |

- **Lifecycle**: Persistent with retention limit (90 days default)
- **Ownership**: System-managed
- **Deletion**: Retained per policy; reporter/reported user deletion anonymizes but retains for safety

### ModerationEvent

| Field | Type | Privacy | Description |
|---|---|---|---|
| `id` | `str` (UUID) | Internal | Event identifier |
| `report_id` | `str` (FK, optional) | Internal | Related report |
| `target_user_id` | `str` (FK) | Internal | User affected |
| `action` | `ModAction` enum | Internal | `WARNING`, `TEMP_SUSPEND`, `PERMANENT_BAN`, `CLEARED` |
| `admin_id` | `str` (optional) | Internal | Admin who took action |
| `reason` | `str` | Internal | Explanation |
| `created_at` | `datetime` | Internal | When action was taken |

- **Lifecycle**: Persistent
- **Classification**: Future (post-MVP admin tools)

### RateLimitState

| Field | Type | Privacy | Description |
|---|---|---|---|
| `user_id` | `str` | Internal | Rate-limited user |
| `action` | `str` | Internal | Action being limited (message, match, report) |
| `window_start` | `datetime` | Internal | Current window start |
| `count` | `int` | Internal | Actions in current window |

- **Lifecycle**: Ephemeral (in-memory) or short-lived persistent
- **Deletion**: Expires automatically

### UserSettings

| Field | Type | Privacy | Description |
|---|---|---|---|
| `user_id` | `str` (FK) | Internal | References `User.id` |
| `notifications_enabled` | `bool` | Internal | Receive match notifications |
| `icebreakers_enabled` | `bool` | Internal | Show conversation starters |

- **Lifecycle**: Persistent; 1:1 with User
- **Deletion**: Deleted with User

### GameSession

| Field | Type | Privacy | Description |
|---|---|---|---|
| `id` | `str` (UUID) | Internal | Game session identifier |
| `chat_session_id` | `str` (FK) | Internal | Parent chat session |
| `game_type` | `GameType` enum | Internal | `TIC_TAC_TOE`, future types |
| `status` | `GameStatus` enum | Internal | `INVITED`, `ACCEPTED`, `ACTIVE`, `COMPLETED`, `CANCELLED` |
| `created_at` | `datetime` | Internal | Game creation time |
| `ended_at` | `datetime` (optional) | Internal | Game end time |

- **Lifecycle**: Persistent (metadata)
- **Deletion**: Deleted with parent chat session or user

### GameParticipant

| Field | Type | Privacy | Description |
|---|---|---|---|
| `game_id` | `str` (FK) | Internal | References `GameSession.id` |
| `user_id` | `str` (FK) | Internal | References `User.id` |
| `symbol` | `str` | Internal | Game-specific (e.g., "X" or "O") |
| `is_current_turn` | `bool` | Internal | Whether it's this player's turn |

- **Lifecycle**: Persistent; exactly 2 per GameSession
- **Deletion**: Deleted with game session

### GameState

| Field | Type | Privacy | Description |
|---|---|---|---|
| `game_id` | `str` (FK) | Internal | References `GameSession.id` |
| `board` | `str` (JSON) | Internal | Serialized board state |
| `turn_number` | `int` | Internal | Current turn |
| `winner_id` | `str` (optional) | Internal | Winner user ID |
| `is_draw` | `bool` | Internal | Whether game ended in draw |

- **Lifecycle**: Persistent
- **Deletion**: Deleted with game session

### GameAction

| Field | Type | Privacy | Description |
|---|---|---|---|
| `id` | `str` (UUID) | Internal | Action identifier |
| `game_id` | `str` (FK) | Internal | References `GameSession.id` |
| `user_id` | `str` (FK) | Internal | Acting player |
| `action_data` | `str` (JSON) | Internal | Move details (e.g., position) |
| `turn_number` | `int` | Internal | Turn this action was for |
| `created_at` | `datetime` | Internal | When action was submitted |

- **Lifecycle**: Persistent
- **Deletion**: Deleted with game session

### FeatureFlag

| Field | Type | Privacy | Description |
|---|---|---|---|
| `name` | `str` | Internal | Flag identifier |
| `enabled` | `bool` | Internal | Whether feature is active |
| `description` | `str` | Internal | Human-readable description |

- **Lifecycle**: Persistent
- **Classification**: Post-MVP

### AuditEvent

| Field | Type | Privacy | Description |
|---|---|---|---|
| `id` | `str` (UUID) | Internal | Event identifier |
| `user_id` | `str` (optional) | Internal | Related user |
| `event_type` | `str` | Internal | Event category |
| `details` | `str` (JSON) | Internal | Redacted event details |
| `created_at` | `datetime` | Internal | Timestamp |

- **Lifecycle**: Persistent with retention limit
- **Classification**: Post-MVP

### ConsentRecord (Future)

| Field | Type | Privacy | Description |
|---|---|---|---|
| `user_id` | `str` (FK) | Internal | References `User.id` |
| `consent_type` | `str` | Internal | What was consented to |
| `granted` | `bool` | Internal | Consent state |
| `granted_at` | `datetime` | Internal | When consent was given |
| `revoked_at` | `datetime` (optional) | Internal | When consent was revoked |

- **Lifecycle**: Future
- **Classification**: Future

### PremiumEntitlement (Future)

- **Lifecycle**: Future
- **Classification**: Future — design only in [Product Requirements](01-product-requirements.md)

### PaymentTransaction (Future)

- **Lifecycle**: Future
- **Classification**: Future — design only

### BotConfiguration

| Field | Type | Privacy | Description |
|---|---|---|---|
| `key` | `str` | Internal | Configuration key |
| `value` | `str` | Internal | Configuration value |
| `updated_at` | `datetime` | Internal | Last update |

- **Lifecycle**: Persistent
- **Ownership**: Admin-managed

### ProviderConfiguration

| Field | Type | Privacy | Description |
|---|---|---|---|
| `provider_name` | `str` | Internal | AI provider identifier |
| `enabled` | `bool` | Internal | Whether provider is active |
| `model` | `str` | Internal | Model identifier |
| `max_tokens` | `int` | Internal | Token limit per request |
| `timeout_seconds` | `int` | Internal | Request timeout |
| `daily_quota` | `int` | Internal | Max requests per day |

- **Lifecycle**: Persistent (or environment-configured)
- **Classification**: Post-MVP (Phase 6)

---

## Enumerations

```python
class UserStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"

class AgeRange(str, Enum):
    AGE_18_24 = "18_24"
    AGE_25_34 = "25_34"
    AGE_35_44 = "35_44"
    AGE_45_PLUS = "45_plus"

class SessionStatus(str, Enum):
    MATCHING = "matching"
    ACTIVE = "active"
    ENDING = "ending"
    ENDED = "ended"

class EndReason(str, Enum):
    USER_NEXT = "user_next"
    USER_STOP = "user_stop"
    PARTNER_LEFT = "partner_left"
    TIMEOUT = "timeout"
    BLOCK = "block"
    ADMIN = "admin"

class ReportCategory(str, Enum):
    HARASSMENT = "harassment"
    SPAM = "spam"
    SEXUAL_CONTENT = "sexual_content"
    SUSPECTED_MINOR = "suspected_minor"
    IMPERSONATION = "impersonation"
    EXPLOITATION = "exploitation"
    OTHER = "other"

class GameType(str, Enum):
    TIC_TAC_TOE = "tic_tac_toe"

class GameStatus(str, Enum):
    INVITED = "invited"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
```

---

## Data Classification Summary

| Classification | Entities | Handling |
|---|---|---|
| **Private (Never Exposed)** | `telegram_id`, `User.id` mappings | Internal only; never in API responses to other users |
| **Internal** | Session IDs, game state, preferences | Backend use only; not shared between users |
| **Shared on Consent** | `display_name`, `bio` | Only shared if both users consent to mutual reveal |
| **Public** | Interest catalog | Available to all authenticated users |
| **Ephemeral** | MessageEnvelope, RateLimitState | Never persisted; in-memory only |
| **Sensitive** | Report descriptions, moderation events | Access-controlled; retention-limited |

---

## Related Documents

- [Entity Relationships](08-entity-relationships.md)
- [State Machines](10-state-machines.md)
- [Privacy & Data Governance](19-privacy-and-data-governance.md)
- [Storage & Persistence](20-storage-and-persistence.md)
