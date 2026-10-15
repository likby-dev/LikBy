# 18 — Security Threat Model

## Purpose

Analyze threats using STRIDE methodology and map each threat to controls, code locations, and tests.

## Scope

Covers the MVP Telegram bot and identified future attack surfaces.

---

## STRIDE Analysis

### S — Spoofing

| # | Threat | Impact | Likelihood | Controls | Tests |
|---|---|---|---|---|---|
| S-1 | Forged webhook requests | Attacker sends fake Telegram updates | Medium | Verify `X-Telegram-Bot-Api-Secret-Token` on every request | Test: request without token → 403 |
| S-2 | Replayed webhook requests | Old updates processed again | Low | Track `update_id`; skip duplicates | Test: same update_id twice → second ignored |
| S-3 | Admin command spoofing | Non-admin sends admin commands | Medium | Check `telegram_id` against `ADMIN_TELEGRAM_IDS` | Test: non-admin user → denied |
| S-4 | Future: forged Mini App initData | Attacker bypasses Mini App auth | High | HMAC verification of initData server-side | Documented for Phase 9 |
| S-5 | Future: forged JWT tokens | Access web API as another user | High | Standard JWT signing/verification | Documented for Phase 9 |

### T — Tampering

| # | Threat | Impact | Likelihood | Controls | Tests |
|---|---|---|---|---|---|
| T-1 | Malicious callback data | Attacker modifies inline keyboard callbacks | Medium | Server re-validates all callback data; never trust client state | Test: invalid callback data → rejected |
| T-2 | Game state manipulation | Player sends forged board/winner | High | Server-authoritative game state; validate every move | Test: illegal move → rejected |
| T-3 | Profile injection | Malicious content in display name/bio | Medium | Pydantic validation; HTML escaping; length limits | Test: XSS payload in name → escaped |
| T-4 | SQLite injection | Malicious input in queries | High | Parameterized queries only (never string concat) | Test: SQL injection patterns → parameterized |

### R — Repudiation

| # | Threat | Impact | Likelihood | Controls | Tests |
|---|---|---|---|---|---|
| R-1 | User denies sending reported message | Cannot prove message content | Medium | Design choice: no message persistence protects privacy; accept limited evidence | Documented trade-off |
| R-2 | Admin denies moderation action | Accountability gap | Low | Audit log for moderation events | Test: moderation creates AuditEvent |

### I — Information Disclosure

| # | Threat | Impact | Likelihood | Controls | Tests |
|---|---|---|---|---|---|
| I-1 | Telegram ID exposure | User's Telegram account revealed to partner | **Critical** | Internal opaque IDs only; telegram_id never in responses | Test: no telegram_id in any bot message |
| I-2 | Cross-session message leakage | User sees messages from another session | **Critical** | Session participant verification on every relay | Test: message to wrong session → blocked |
| I-3 | Secrets in logs | BOT_TOKEN, webhook secret in log output | High | Structured logging with redaction filter | Test: grep logs for token patterns → none found |
| I-4 | Message content in logs | Private conversations in log files | High | Never log message text; only metadata | Test: message relay doesn't log content |
| I-5 | Error messages expose internals | Stack traces shown to users | Medium | Generic error messages; detailed errors in logs only | Test: DB error → user sees "something went wrong" |
| I-6 | Session enumeration | Attacker guesses session IDs | Low | UUID session IDs (128-bit entropy) | Test: random UUID → not guessable |

### D — Denial of Service

| # | Threat | Impact | Likelihood | Controls | Tests |
|---|---|---|---|---|---|
| D-1 | Message spam | Flood messages to exhaust resources | Medium | Per-user rate limiting (30 msg/min) | Test: 31st message → rate limited |
| D-2 | Match queue spam | Rapid join/leave cycling | Medium | Rate limit match requests (10/5min) | Test: 11th match request → rate limited |
| D-3 | Report flooding | Overwhelm moderation queue | Low | Rate limit reports (3/hour) | Test: 4th report → rate limited |
| D-4 | Large message payloads | Memory exhaustion | Low | Telegram limits message size; additional server-side check | Test: oversized payload → rejected |
| D-5 | Callback spam | Rapid button clicks | Medium | Rate limit callbacks | Test: excessive callbacks → throttled |

### E — Elevation of Privilege

| # | Threat | Impact | Likelihood | Controls | Tests |
|---|---|---|---|---|---|
| E-1 | Non-participant accesses session | Read/modify another user's chat | **Critical** | Participant verification on every operation | Test: non-participant → forbidden |
| E-2 | Regular user accesses admin functions | Unauthorized moderation | High | Admin ID verification | Test: non-admin → rejected |
| E-3 | Player submits opponent's move | Game manipulation | Medium | Turn ownership verification in GameService | Test: wrong player's move → rejected |
| E-4 | IDOR: accessing other user's profile | Privacy violation | High | User can only access own profile via authenticated ID | Test: profile request for other user → denied |

---

## Security Requirements Matrix

| Threat | Control | Code Location | Test Location |
|---|---|---|---|
| S-1 | Webhook secret verification | `api/webhook.py` | `tests/unit/test_webhook_security.py` |
| S-2 | Update ID deduplication | `telegram/middleware.py` | `tests/unit/test_dedup.py` |
| S-3 | Admin ID check | `telegram/handlers/admin.py` | `tests/unit/test_admin_auth.py` |
| T-1 | Callback validation | `telegram/handlers/*.py` | `tests/unit/test_callbacks.py` |
| T-2 | Server-side game state | `domain/games/tictactoe.py` | `tests/unit/test_tictactoe.py` |
| T-3 | Input validation + escaping | `services/user_service.py` | `tests/unit/test_profile_validation.py` |
| T-4 | Parameterized queries | `repositories/sqlite/*.py` | `tests/integration/test_sql_injection.py` |
| I-1 | Opaque ID mapping | `services/chat_service.py` | `tests/unit/test_no_telegram_id_leak.py` |
| I-2 | Session participant check | `services/chat_service.py` | `tests/unit/test_session_isolation.py` |
| I-3 | Log redaction | `observability/logging.py` | `tests/unit/test_log_redaction.py` |
| I-4 | No content logging | `services/chat_service.py` | `tests/unit/test_no_content_log.py` |
| D-1 | Rate limiting | `security/rate_limiter.py` | `tests/unit/test_rate_limits.py` |
| E-1 | Participant verification | `services/chat_service.py` | `tests/unit/test_session_access.py` |
| E-2 | Admin verification | `telegram/middleware.py` | `tests/unit/test_admin_auth.py` |
| E-3 | Turn ownership | `services/game_service.py` | `tests/unit/test_game_auth.py` |

---

## Residual Risks

| Risk | Severity | Mitigation Status | Notes |
|---|---|---|---|
| Telegram itself can read all messages | High | **Accepted** — documented in privacy notice | Cannot mitigate without E2E encryption (not available for bots) |
| Screenshots by conversation partner | Medium | **Accepted** — documented in privacy notice | Cannot prevent client-side recording |
| Determined minor bypasses age self-declaration | Medium | **Accepted** — documented limitation | True verification requires invasive ID checks |
| Free-tier host restarts lose all data | High | **Accepted for demo** — production requires external DB | See [Storage & Persistence](20-storage-and-persistence.md) |
| Single-instance SQLite under concurrent load | Medium | **Accepted for MVP** — `BEGIN IMMEDIATE` + `busy_timeout` | Migration to PostgreSQL for production |

---

## Related Documents

- [Authentication & Authorization](13-authentication-and-authorization.md)
- [Privacy & Data Governance](19-privacy-and-data-governance.md)
- [Testing & Quality](25-testing-and-quality.md)
- [Configuration & Secrets](31-configuration-and-secrets.md)
- [Risk Register](37-risk-register.md)
