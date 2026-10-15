# 36 — Acceptance Criteria

## Purpose

Define the formal Definition of Done (DoD), functional acceptance criteria, and Given-When-Then behavior specifications for the LikBy MVP launch.

## Scope

Covers user onboarding, matchmaking, real-time message relay, multiplayer games, abuse moderation, privacy guarantees, and operational readiness.

---

## Global Definition of Done (DoD)

A feature or pull request is considered **DONE** only when:
1. **Code Quality**: Passes `ruff check` and `ruff format --check` with zero warnings.
2. **Type Safety**: Passes `mypy --strict` with zero type errors.
3. **Test Coverage**: Unit and integration test coverage meets or exceeds 85% project-wide and 90% for domain logic.
4. **Privacy Validation**: Automated tests verify that no private message text is written to persistent logs or database tables.
5. **Documentation**: Any schema changes, API routes, or configuration variables are documented in the corresponding markdown files in `docs/`.

---

## Behavior-Driven Acceptance Specifications

### 1. User Onboarding & Age Verification Gate

```gherkin
Scenario: New adult user successfully completes age gate and onboarding
  Given a new user who sends "/start" to the bot
  Then the bot presents the welcome message and asks for age verification
  When the user taps "[ ✅ I am 18 or older ]"
  Then the user's state transitions to "ONBOARDING_AGE_VERIFIED"
  And the bot prompts for a display alias
  When the user sends "Alex_99"
  Then the bot prompts for age and gender
  When the user completes age, gender, and selects 3 interests
  Then a new User and Profile record is persisted
  And the user state becomes "ACTIVE"
  And the bot displays the Main Menu persistent reply keyboard

Scenario: Underage user attempts registration
  Given a new user who sends "/start" to the bot
  When the user taps "[ ❌ I am under 18 ]"
  Then the bot displays: "LikBy is strictly for adults (18+)."
  And no active profile is created
  And the user cannot enter the matchmaking queue
```

### 2. Matchmaking Queue & Mutual Compatibility

```gherkin
Scenario: Compatible users match successfully
  Given User A (English, interests: [Gaming, Tech]) is in the WAITING queue
  And User B (English, interests: [Tech, Music]) enters the queue with overlapping preferences
  When the matchmaking engine evaluates compatibility
  Then the match score is calculated above the threshold (score >= 0.5)
  And a new ChatSession is created with status "ACTIVE"
  And both match tickets are marked "MATCHED"
  And both User A and User B receive the match notification with common interests highlighted
  And both users receive the active chat control keyboard

Scenario: User cancels match search
  Given a user waiting in the matchmaking queue
  When the user taps "[ ❌ Cancel Search ]"
  Then the match ticket status transitions to "CANCELLED"
  And the user state transitions back to "ACTIVE"
  And the bot displays the Main Menu
```

### 3. Anonymous Chat Relay & Privacy Verification

```gherkin
Scenario: Relaying text messages anonymously
  Given User A and User B are in an ACTIVE ChatSession
  When User A sends a text message "Hey, what are you playing?"
  Then the bot forwards the message to User B without User A's identity or username
  And the ChatSession last_activity_at timestamp is updated
  And message_count is incremented by 1
  And the text body "Hey, what are you playing?" is NOT saved anywhere in the database

Scenario: Inactivity timeout warning and closure
  Given an ACTIVE ChatSession with no messages for 4 minutes
  When the session expiry monitor runs
  Then both users receive an inactivity reminder warning
  When an additional 1 minute passes with no messages
  Then the ChatSession is transitioned to "ENDED" with reason "INACTIVITY_TIMEOUT"
  And both users are notified that the session has concluded
```

### 4. Multiplayer Tic-Tac-Toe

```gherkin
Scenario: Completing a game of Tic-Tac-Toe
  Given an ACTIVE ChatSession between Player X and Player O
  When Player X challenges Player O to Tic-Tac-Toe
  And Player O accepts
  Then an inline 3x3 keyboard is rendered for both players
  When Player X makes move at (row: 0, col: 0)
  Then the cell is updated with "❌"
  And the turn shifts to Player O
  When Player O attempts to play in (row: 0, col: 0)
  Then an alert is displayed: "That space is already occupied!"
  And the game state remains unchanged
```

### 5. Abuse Reporting & Safety Blocking

```gherkin
Scenario: Reporting an abusive partner
  Given User A is in an ACTIVE ChatSession with User B
  When User A executes "/report" and selects category "HARASSMENT"
  Then a new Report record is created
  And the current ChatSession is immediately terminated
  And an entry is added to user_blocks preventing User A and User B from ever matching again
  And User B's report count is incremented
  And User A is returned to the Main Menu with safety resources
```

---

## Operational Verification Criteria

- [ ] **Webhook Latency**: p95 acknowledgment time to Telegram is < 50ms under a load of 50 concurrent requests.
- [ ] **Health Check Resiliency**: `GET /health/ready` returns HTTP 200 when database and Telegram APIs are reachable, and HTTP 503 if the database file is locked or unavailable.
- [ ] **Container Restart**: If the container process restarts, the application cleanly boots, re-verifies the webhook with Telegram, and handles new updates without manual intervention.
