# 33 — Incident Response

## Purpose

Define the incident severity classifications, triage procedures, operational kill switches, escalation paths, and postmortem guidelines for Tikible.

## Scope

Covers security breaches, system outages, abuse outbreaks, platform-level Telegram bans, and data integrity incidents.

---

## Severity Classification Matrix

| Level | Impact | Examples | Target Response | Target Resolution |
|---|---|---|---|---|
| **SEV-1 (Critical)** | Core system completely down, active data compromise, or platform ban | Bot token revoked, Telegram API blocking webhook, database corruption, remote code execution | **< 15 minutes** | **< 2 hours** |
| **SEV-2 (High)** | Major subsystem broken, affecting majority of users | Matchmaker deadlocked, message relay failure rate > 10%, high spam wave bypass | **< 30 minutes** | **< 6 hours** |
| **SEV-3 (Medium)** | Non-critical feature broken or degraded experience | Multiplayer games failing, AI icebreakers failing (fallback working), slow latency | **< 2 hours** | **< 24 hours** |
| **SEV-4 (Low)** | Minor bug, cosmetic issue, or typo | Profile bio text formatting glitch, localized UI copy typo | **< 24 hours** | Next Release Cycle |

---

## Operational Kill Switches

Tikible implements runtime circuit-breaker flags stored in memory or fast environment config to isolate subsystems without taking down the entire service:

```python
# src/tikible/config.py / app state circuit breakers
class FeatureFlags:
    GLOBAL_BOT_ENABLED: bool = True       # Master switch: returns maintenance message to all updates
    MATCHMAKING_ENABLED: bool = True     # Pauses /find queue; active chats continue unaffected
    CHAT_RELAY_ENABLED: bool = True      # Suspends message forwarding in emergencies
    GAMES_ENABLED: bool = True           # Disables Tic-Tac-Toe invites
    AI_ICEBREAKERS_ENABLED: bool = True  # Disables LLM calls; uses hardcoded static prompts
```

### Triggering Emergency Kill Switch
1. In Render Dashboard -> Environment:
   ```env
   MATCHMAKING_ENABLED=false
   ```
2. Trigger manual redeploy. The bot immediately starts responding to `/find`:
   > <i>⚠️ Matchmaking is temporarily paused for scheduled maintenance. Please check back shortly!</i>

---

## Emergency Playbooks

### Playbook A: Coordinated Spam / Abuse Outbreak
1. **Activate Strict Rate Limiter**: Lower user message quota to 2 messages per 10 seconds.
2. **Enable Captcha Onboarding Gate**: Require new users to complete a 3-question math/word challenge before profile activation.
3. **Admin Mass-Ban**:
   ```sql
   UPDATE users SET status = 'BANNED', ban_reason = 'SPAM_CLUSTER_INCIDENT'
   WHERE id IN (SELECT reported_id FROM reports WHERE status = 'PENDING' GROUP BY reported_id HAVING COUNT(*) >= 3);
   ```

### Playbook B: Telegram Bot API HTTP 429 (Flood Control Exceeded)
1. Telegram enforces a 30 messages/sec global outbound limit.
2. If HTTP 429 is received:
   - Read `parameters.retry_after` from Telegram error response.
   - Circuit breaker automatically throttles outbound HTTP requests across all workers for the specified duration.
   - Notify in-chat users with a single throttled status update.

### Playbook C: Bot Token Compromise
1. Immediately log in to `@BotFather` on Telegram.
2. Send `/revoke` to invalidate the active token.
3. Generate a new token and update `BOT_TOKEN` in Render secrets.
4. Review access logs for any unauthorized `sendMessage` or `setWebhook` activity during the window of exposure.

---

## Postmortem Protocol & Template

A blameless postmortem MUST be completed within 48 hours for all SEV-1 and SEV-2 incidents.

### Postmortem Template
```markdown
# Incident Postmortem: [Title / Date]

**Date:** 2026-XX-XX  
**Severity:** SEV-1 / SEV-2  
**Lead Investigator:** @name  
**Duration:** Start: HH:MM UTC | End: HH:MM UTC (Total: Xh Ym)

## Executive Summary
Brief summary of what broke, the user impact, and how it was resolved.

## Impact Metrics
- Users impacted: X
- Failed messages / matches: Y
- Total downtime: Z minutes

## Root Cause Analysis (5 Whys)
1. Why did the service fail? ...
2. Why? ...
3. Why? ...
4. Why? ...
5. Why? ...

## Timeline of Events
- 14:02 UTC - Alerts fired on Discord / BetterStack
- 14:10 UTC - On-call engineer investigated logs
- 14:18 UTC - Kill switch activated
- 14:35 UTC - Patch deployed
- 14:40 UTC - Health checks green; service restored

## Corrective Actions & Action Items
- [ ] Task 1: Add automated alert for metric (Owner, Due Date)
- [ ] Task 2: Implement regression test (Owner, Due Date)
```
