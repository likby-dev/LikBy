# 09 — Data Flow

## Purpose

Document the sequence of operations for every major user flow, identifying actors, validation, state changes, storage operations, and error handling.

## Scope

Covers all MVP flows and selected future flows for architectural reference.

---

## 1. `/start` and Onboarding

```mermaid
sequenceDiagram
    participant U as User
    participant T as Telegram
    participant A as Telegram Adapter
    participant US as User Service
    participant R as User Repository
    participant DB as SQLite

    U->>T: /start
    T->>A: Webhook update (message: /start)
    A->>US: handle_start(telegram_id)
    US->>R: get_by_telegram_id(telegram_id)
    R->>DB: SELECT * FROM users WHERE telegram_id = ?
    DB-->>R: null (new user)
    R-->>US: None

    Note over US: New user — begin onboarding
    US->>R: create(User{telegram_id, status=PENDING})
    R->>DB: INSERT INTO users ...
    DB-->>R: OK
    R-->>US: User

    US-->>A: OnboardingResponse(show_welcome=true)
    A->>T: Send welcome message + privacy notice
    T->>U: "Welcome to Tikible! ..."
    A->>T: Send age eligibility inline keyboard
    T->>U: "Are you 18 or older?" [Yes] [No]
```

**Returning user flow:**
```mermaid
sequenceDiagram
    participant U as User
    participant A as Telegram Adapter
    participant US as User Service
    participant R as User Repository

    Note over A: User found in DB with onboarding_complete=true
    US-->>A: WelcomeBackResponse
    A->>U: "Welcome back! Use /help for commands."
```

### Flow Details

| Aspect | Detail |
|---|---|
| **Initiating Actor** | User |
| **Input** | `/start` command |
| **Validation** | Telegram update verified via webhook secret |
| **Auth** | Telegram identity (internal mapping) |
| **Transaction** | Single INSERT for new user |
| **State Change** | User: (none) → PENDING |
| **Error** | DB failure → "Sorry, please try again later" |
| **Idempotency** | Re-sending `/start` for existing user returns welcome-back |
| **Data NOT Persisted** | Message content |

---

## 2. Profile Creation

```mermaid
sequenceDiagram
    participant U as User
    participant A as Telegram Adapter
    participant US as User Service
    participant R as User Repository

    U->>A: Age check: "Yes, I'm 18+"
    A->>US: confirm_eligibility(user_id)
    US->>R: update(user{is_eligible=true})
    R-->>US: OK

    A->>U: "Great! Let's set up your profile."
    A->>U: "Choose a display name:"
    U->>A: "Alex"
    A->>US: create_profile(user_id, display_name="Alex")
    US->>R: create(UserProfile{...})

    A->>U: "Select your interests:" [keyboard]
    U->>A: Callback: interests selected
    A->>US: set_interests(user_id, ["music", "travel"])

    A->>US: complete_onboarding(user_id)
    US->>R: update(user{onboarding_complete=true, status=ACTIVE})
    A->>U: "Profile complete! Use /next to find a match."
```

| Aspect | Detail |
|---|---|
| **Transaction** | Profile + interests + status update in single transaction |
| **State Change** | User: PENDING → ACTIVE |
| **Validation** | Display name: 2–30 chars, no URLs, no prohibited patterns |
| **Error** | Invalid name → re-prompt with explanation |

---

## 3. Joining the Matching Queue

```mermaid
sequenceDiagram
    participant U as User
    participant A as Telegram Adapter
    participant MS as Matching Service
    participant QR as Queue Repository
    participant SR as Session Repository
    participant BR as Block Repository
    participant ME as Match Engine

    U->>A: /next (or "Find match" button)
    A->>MS: join_queue(user_id)

    MS->>SR: get_active_by_user(user_id)
    Note over MS: Check if already in active session

    alt Already in session
        MS-->>A: Error: already in session
        A->>U: "You're already chatting! Use /stop first."
    else No active session
        MS->>QR: is_queued(user_id)
        alt Already queued
            MS-->>A: AlreadyQueued
            A->>U: "You're already waiting for a match..."
        else Not queued
            MS->>QR: enqueue(QueueEntry{user_id, joined_at, expires_at})
            MS->>BR: get_blocked_by(user_id)
            MS->>QR: find_candidates(user, exclude=blocked_ids)

            alt Candidate found
                MS->>ME: calculate_score(user, candidate)
                MS->>MS: create_match(user, candidate) — ATOMIC
                Note over MS: See "Atomic Match Creation" below
            else No candidate
                MS-->>A: Queued(position, estimated_wait)
                A->>U: "Looking for a match... ⏳"
            end
        end
    end
```

---

## 4. Atomic Match Creation

```mermaid
sequenceDiagram
    participant MS as Matching Service
    participant QR as Queue Repository
    participant SR as Session Repository
    participant DB as SQLite

    Note over MS,DB: BEGIN IMMEDIATE TRANSACTION

    MS->>QR: dequeue(user_a_id)
    MS->>QR: dequeue(user_b_id)

    Note over MS: Verify both still queued (guard against race)

    alt Either user no longer queued
        MS->>DB: ROLLBACK
        MS-->>MS: MatchFailed — retry with next candidate
    else Both still queued
        MS->>SR: create(ChatSession{status=ACTIVE})
        MS->>SR: add_participant(session, user_a, PARTICIPANT_A)
        MS->>SR: add_participant(session, user_b, PARTICIPANT_B)
        MS->>DB: COMMIT

        MS-->>MS: MatchSuccess(session_id)
    end
```

### Concurrency Safety

| Invariant | Enforcement |
|---|---|
| User cannot be matched twice | `BEGIN IMMEDIATE` + verify-then-commit |
| Self-matching impossible | Candidate query excludes requesting user |
| Blocked users excluded | Block check before candidate selection |
| Active session prevents queue join | Session check at queue entry |
| Stale queue entries cleaned | `expires_at` checked; periodic cleanup |
| Webhook retries safe | `update_id` deduplication prevents double-processing |

---

## 5. Message Relay

```mermaid
sequenceDiagram
    participant U1 as User A
    participant T as Telegram
    participant A as Telegram Adapter
    participant CS as Chat Service
    participant SR as Session Repository
    participant U2 as User B

    U1->>T: "Hello!"
    T->>A: Webhook: text message from User A
    A->>CS: relay_message(sender_telegram_id, text)
    CS->>SR: get_active_by_user(sender_user_id)

    alt No active session
        CS-->>A: Error: not in session
        A->>U1: "You're not in a chat. Use /next to find a match."
    else Active session found
        CS->>CS: Find partner user_id from session participants
        CS->>CS: Look up partner's telegram_id
        Note over CS: Message content NEVER persisted
        CS-->>A: RelayResult(partner_telegram_id, text)
        A->>T: bot.send_message(partner_telegram_id, text)
        T->>U2: "Hello!" (from anonymous partner)
    end
```

| Aspect | Detail |
|---|---|
| **Auth** | Sender must be participant in the active session |
| **Content** | Text only (MVP); media handling is future |
| **Persistence** | **NOTHING stored** — message relayed and discarded |
| **Rate Limit** | Max 30 messages/minute per user |
| **Error** | Partner blocked bot → notify sender "Partner unavailable" |

---

## 6. `/stop` — End Session

```mermaid
sequenceDiagram
    participant U as User
    participant A as Telegram Adapter
    participant CS as Chat Service
    participant SR as Session Repository

    U->>A: /stop
    A->>CS: end_session(user_id, reason=USER_STOP)
    CS->>SR: get_active_by_user(user_id)

    alt No active session
        CS-->>A: Error: not in session
        A->>U: "You're not in a chat right now."
    else Active session
        CS->>SR: update_status(session_id, ENDED)
        CS->>SR: set_left_at(session_id, user_id)
        CS->>SR: set_left_at(session_id, partner_id)
        CS-->>A: SessionEnded(partner_telegram_id)
        A->>U: "Chat ended. Use /next to find a new match."
        A->>Partner: "Your partner has left the chat."
    end
```

---

## 7. `/next` — End and Re-queue

```mermaid
sequenceDiagram
    participant U as User
    participant A as Telegram Adapter
    participant CS as Chat Service
    participant MS as Matching Service

    U->>A: /next
    A->>CS: end_session(user_id, reason=USER_NEXT)
    Note over CS: Same as /stop but also...
    A->>MS: join_queue(user_id)
    Note over MS: Immediately attempt to find new match
```

| Aspect | Detail |
|---|---|
| **Transaction** | End session + enqueue in atomic transaction |
| **State Change** | Session: ACTIVE → ENDED; User → queued |
| **Race Condition** | `/next` while being matched by another user — handle via BEGIN IMMEDIATE |

---

## 8. Blocking a Participant

```mermaid
sequenceDiagram
    participant U as User
    participant A as Telegram Adapter
    participant SS as Safety Service
    participant BR as Block Repository
    participant CS as Chat Service

    U->>A: /block
    A->>SS: block_current_partner(user_id)
    SS->>CS: get_active_session(user_id)
    SS->>SS: Identify partner from session
    SS->>BR: block(blocker_id=user_id, blocked_id=partner_id)
    SS->>CS: end_session(session_id, reason=BLOCK)
    SS-->>A: BlockResult(success=true)
    A->>U: "User blocked. You won't be matched with them again."
    A->>Partner: "Your partner has left the chat."
```

| Aspect | Detail |
|---|---|
| **Privacy** | Partner is NOT told they were blocked; message says "left" |
| **Transaction** | Block + session end atomic |
| **Idempotency** | Blocking already-blocked user is a no-op |

---

## 9. Reporting Abuse

```mermaid
sequenceDiagram
    participant U as User
    participant A as Telegram Adapter
    participant SS as Safety Service
    participant RR as Report Repository

    U->>A: /report
    A->>U: "Select reason:" [Harassment] [Spam] [Sexual] [Minor] [Other]
    U->>A: Callback: "harassment"
    A->>U: "Add details (optional, or /skip):"
    U->>A: "They were threatening me"

    A->>SS: create_report(reporter_id, reported_id, session_id, category, description)
    SS->>RR: create(Report{...})
    SS-->>A: ReportCreated
    A->>U: "Report submitted. Thank you for helping keep Tikible safe."
```

| Aspect | Detail |
|---|---|
| **Retention** | Reports retained 90 days then anonymized |
| **Content** | Description may contain sensitive content — stored encrypted at rest when possible |
| **Access** | Only admin can view reports |
| **No auto-action** | Reports are not auto-actioned; human review required |

---

## 10. Account Deletion

```mermaid
sequenceDiagram
    participant U as User
    participant A as Telegram Adapter
    participant US as User Service
    participant R as Repositories

    U->>A: /delete
    A->>U: "Are you sure? This permanently deletes all your data." [Yes, delete] [Cancel]
    U->>A: Callback: "confirm_delete"
    A->>US: delete_account(user_id)

    US->>R: End active sessions
    US->>R: Remove from queue
    US->>R: Delete profile, preferences, settings, interests
    US->>R: Delete blocks (where blocker)
    US->>R: Anonymize reports (SET NULL user references)
    US->>R: Delete user record

    US-->>A: AccountDeleted
    A->>U: "Your account and all data have been permanently deleted. Goodbye!"
```

---

## 11. Starting a Multiplayer Game

```mermaid
sequenceDiagram
    participant U1 as User A
    participant A as Telegram Adapter
    participant GS as Game Service
    participant CS as Chat Service

    U1->>A: /play
    A->>CS: get_active_session(user_a_id)
    alt No active session
        A->>U1: "You need to be in a chat to play games."
    else Active session
        A->>U1: "Choose a game:" [Tic-tac-toe]
        U1->>A: Callback: "game_tictactoe"
        A->>GS: invite_game(session_id, inviter_id, game_type=TIC_TAC_TOE)
        GS-->>A: GameInvited(game_id)
        A->>U1: "Game invitation sent! Waiting for partner..."
        A->>U2: "Your partner wants to play Tic-tac-toe!" [Accept] [Decline]
    end
```

---

## 12. Submitting a Game Move

```mermaid
sequenceDiagram
    participant U as User
    participant A as Telegram Adapter
    participant GS as Game Service
    participant GR as Game Rules

    U->>A: Callback: "game_move_4" (position 4 on board)
    A->>GS: submit_move(game_id, user_id, position=4)
    GS->>GS: Verify it's this user's turn
    GS->>GR: validate_move(board_state, position)

    alt Invalid move
        GS-->>A: InvalidMove(reason="Position already taken")
        A->>U: "That position is taken! Choose another."
    else Valid move
        GS->>GR: apply_move(board_state, position, symbol)
        GS->>GR: check_winner(new_board)

        alt Game continues
            GS->>GS: Update state, switch turn
            GS-->>A: MoveResult(new_board, next_turn=partner)
            A->>U: Updated board (inline keyboard)
            A->>Partner: Updated board + "Your turn!"
        else Winner determined
            GS->>GS: End game with result
            GS-->>A: GameOver(winner=user_id)
            A->>U: "You won! 🎉" [Rematch] [Done]
            A->>Partner: "You lost! Better luck next time." [Rematch] [Done]
        end
    end
```

---

## 13. Webhook Verification and Processing

```mermaid
sequenceDiagram
    participant T as Telegram
    participant W as Webhook Endpoint
    participant D as Dispatcher

    T->>W: POST /webhook<br/>Header: X-Telegram-Bot-Api-Secret-Token

    W->>W: Compare header with configured secret

    alt Secret mismatch
        W-->>T: 403 Forbidden
    else Secret valid
        W->>W: Parse JSON body as Telegram Update
        W->>W: Check update_id for deduplication

        alt Duplicate update_id
            W-->>T: 200 OK (idempotent — already processed)
        else New update
            W->>D: Dispatch to aiogram handler
            D-->>W: Handler result
            W-->>T: 200 OK
        end
    end
```

---

## 14. Duplicate Update Handling

| Scenario | Cause | Handling |
|---|---|---|
| Same `update_id` received twice | Telegram retry on timeout | Track recent `update_id`s in memory; skip duplicates |
| `/next` sent twice rapidly | User double-tap | Idempotent — second call sees user already queued |
| Match + `/stop` race | User stops while being matched | `BEGIN IMMEDIATE` ensures atomic state check |
| Block during message relay | Timing overlap | Message delivery failure handled gracefully |

---

## 15. Future: Migration from SQLite to Supabase

```mermaid
sequenceDiagram
    participant OP as Operator
    participant APP as Application
    participant SQ as SQLite
    participant SP as Supabase PostgreSQL

    OP->>APP: Set maintenance mode (reject new matches)
    OP->>SQ: Export all tables to CSV/JSON
    OP->>SP: Create schema (migrations)
    OP->>SP: Import data with transformation
    OP->>SP: Verify row counts and integrity
    OP->>APP: Switch STORAGE_BACKEND=supabase
    OP->>APP: Run integration tests against Supabase
    OP->>APP: Remove maintenance mode
    OP->>OP: Monitor for errors, keep SQLite backup
```

See [Data Migration Runbook](23-data-migration-runbook.md) for complete procedure.

---

## Related Documents

- [Entity Relationships](08-entity-relationships.md)
- [State Machines](10-state-machines.md)
- [Matching Engine](14-matching-engine.md)
- [Chat Session Lifecycle](15-chat-session-lifecycle.md)
- [Multiplayer Games](16-multiplayer-games.md)
- [Performance & Concurrency](26-performance-and-concurrency.md)
