# LikBy QA & Test Strategy Plan

**Platform:** LikBy  
**Last Updated:** 2026-10-19  
**Total Tests:** 171 automated tests across Unit and Integration suites  

---

## 1. Test Layers & Scope

```
┌────────────────────────────────────────────────────────┐
│                   End-to-End Tests                     │
│    (Mini App Static Serving, Telegram Bot Menus)       │
├────────────────────────────────────────────────────────┤
│                API & Integration Tests                 │
│ (Payments, Play Duels, WebSockets, Quotas, Triggers)   │
├────────────────────────────────────────────────────────┤
│                 Domain & Service Tests                 │
│   (Entitlements, Scoring, Matching, Quotas, State)     │
├────────────────────────────────────────────────────────┤
│                Static Checks & Contracts               │
│        (Pydantic Validation, Config, Security)         │
└────────────────────────────────────────────────────────┘
```

---

## 2. Test Execution Commands & Environments

| Test Scope | Command | Purpose |
|---|---|---|
| **Full Suite** | `python -m pytest tests/ -v` | Comprehensive verification of all 171 tests |
| **Quick Sanity** | `python -m pytest tests/ -q` | Fast regression check across all suites |
| **Audit & Hardening** | `python -m pytest tests/integration/test_system_audit_and_hardening.py -v` | Verification of security headers, initData age, WebSocket auth |
| **Profile & Triggers** | `python -m pytest tests/unit/test_profile_expansion.py tests/unit/test_profile.py -v` | Profile expansion, age sync, location and language parsing |
| **Play & Games** | `python -m pytest tests/unit/test_play_games.py tests/integration/test_play_api.py -v` | 18-game catalog, server-authoritative move engines, solo progression |
| **Subscriptions** | `python -m pytest tests/unit/test_subscription_lifecycle.py tests/integration/test_payment_api.py -v` | Tier catalogs, Spark 24h passes, Razorpay webhooks, quota reservation |

---

## 3. Essential Invariants Verified

1. **Zero Data Leakage:** Private user information, chat histories, and profile contact details are never leaked to non-participants or cross-user queries.
2. **Authoritative Entitlement Authority:** Handlers never calculate or award tier limits. All decisions flow through `SubscriptionService`, `MediaQuotaService`, and `GamingEntitlementService`.
3. **Server-Authoritative Game Logic:** Clients submit moves; server engines (`duel_engines.py`, `solo_engines.py`) evaluate valid turns, physics collisions, wins, and draws.
4. **WebSocket Authorization:** Connections without valid identity or connecting to rooms they do not participate in are immediately terminated with WS 1008 Policy Violation.
5. **Replay Protection:** Telegram Mini App `initData` older than 24 hours (86,400 seconds) is rejected.
6. **Database Parity:** Local development in SQLite WAL mode operates with zero cloud credentials while maintaining 100% schema and trigger parity with production Supabase PostgreSQL.

---

## 4. Test Suite Inventory

| Test Module | Test Count | Focus Area |
|---|---|---|
| `tests/integration/test_system_audit_and_hardening.py` | 5 | Security headers, request ID correlation, initData replay, WS auth |
| `tests/integration/test_play_api.py` | 9 | LikBy Play catalog, entitlements, duels, solo games, WebSockets |
| `tests/integration/test_payment_api.py` | 4 | Razorpay orders, signatures, webhooks, subscription status |
| `tests/integration/test_chat_sessions_api.py` | 4 | Transcript delivery, participant authorization, summaries |
| `tests/integration/test_sqlite_repositories.py` | 7 | SQLite schema, WAL mode, migrations, triggers, repositories |
| `tests/integration/test_api.py` | 3 | Health endpoints, webhook authentication, liveness |
| `tests/unit/test_profile_expansion.py` | 8 | DOB calculation, age boundary, location parser, languages |
| `tests/unit/test_profile.py` | 6 | Profile creation, underage rejection, display name updates |
| `tests/unit/test_play_games.py` | 20 | 12 multiplayer duel engines + 6 solo puzzle engines |
| `tests/unit/test_telegram_menu_hubs.py` | 15 | Bot keyboard layouts, menu callbacks, navigation states |
| `tests/unit/test_subscription_lifecycle.py` | 6 | Plan catalog, 24h Spark expiry, quota reservation |
| `tests/unit/test_media_protection_and_quotas.py` | 7 | Media protection flags, daily upload/receive quotas |
| `tests/unit/test_referral_rewards.py` | 4 | Referral link generation, self-referral rejection, Spark grant |
| `tests/unit/test_user.py` | 4 | User lifecycle, age verification, bans, penalties |
| `tests/unit/test_unique_id.py` | 4 | LikBy ID handle regex, immutability, display names |
| `tests/unit/test_scorer.py` | 4 | Compatibility scoring, gender/age/language filters |
| `tests/unit/test_chat_session.py` | 4 | Session transitions, active partner lookups, timeouts |
| `tests/unit/test_solo_games.py` | 5 | Trivia, Gem Hunter, RPS mechanics |
| `tests/unit/test_config.py` | 5 | Settings validation, bot token format, URL canonicalization |
| `tests/unit/test_transcript.py` | 2 | Transcript formatting, Unicode, media labels |
| `tests/unit/test_karma_service.py` | 1 | Rating and karma calculations |
| `tests/unit/test_social_service.py` | 1 | Mutual likes, friendship limits |
| `tests/unit/test_gameverse_platform.py` | 8 | Progression, XP, Leveling, Daily Riddle |
