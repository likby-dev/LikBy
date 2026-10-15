# 14 — Matching Engine

## Purpose

Define the deterministic, testable matching algorithm with scoring model, eligibility rules, fairness considerations, and worked examples.

## Scope

Covers the MVP matching engine. AI-enhanced matching is documented in [AI & ML Strategy](17-ai-and-ml-strategy.md) as a future enhancement.

---

## Architecture Overview

```mermaid
graph LR
    JQ["Join Queue"] --> EC["Eligibility Check"]
    EC --> CS["Candidate Selection"]
    CS --> SC["Scoring"]
    SC --> BM["Best Match Selection"]
    BM --> AM["Atomic Match Creation"]
```

---

## Eligibility Check (Hard Constraints)

These are **binary pass/fail** checks. Failing any one excludes a candidate. AI cannot override these.

| # | Constraint | Enforcement |
|---|---|---|
| E-1 | User status is ACTIVE | Query filter |
| E-2 | User has completed onboarding | `onboarding_complete = true` |
| E-3 | User is eligible (age check passed) | `is_eligible = true` |
| E-4 | User does not have an active session | `get_active_by_user` returns None |
| E-5 | User is not the requesting user | Exclude `self.user_id` |
| E-6 | User is not blocked by or blocking the requester | Block check both directions |
| E-7 | User is in the match queue | Must have QueueEntry |

---

## Candidate Selection

After eligibility filtering, retrieve all remaining candidates from the queue.

```sql
SELECT qe.user_id, qe.joined_at
FROM queue_entries qe
INNER JOIN users u ON qe.user_id = u.id
WHERE u.status = 'active'
  AND u.onboarding_complete = 1
  AND u.is_eligible = 1
  AND qe.user_id != ?  -- not self
  AND qe.user_id NOT IN (SELECT blocked_id FROM blocks WHERE blocker_id = ?)
  AND qe.user_id NOT IN (SELECT blocker_id FROM blocks WHERE blocked_id = ?)
  AND qe.user_id NOT IN (
      SELECT sp.user_id FROM session_participants sp
      INNER JOIN chat_sessions cs ON sp.session_id = cs.id
      WHERE cs.status = 'active'
  )
  AND qe.expires_at > ?  -- not expired
ORDER BY qe.joined_at ASC
```

---

## Scoring Model

### Decision: DECIDED — Weighted multi-signal scoring

Each candidate receives a score from 0.0 to 1.0 based on weighted signals.

### Scoring Variables

| Variable | Symbol | Range | Weight (default) | Description |
|---|---|---|---|---|
| Gender compatibility | `G` | 0.0 or 1.0 | 0.25 | Does candidate match preferred gender (and vice versa)? |
| Age range compatibility | `A` | 0.0 or 1.0 | 0.15 | Does candidate's age range match preference? |
| Shared interests | `I` | 0.0–1.0 | 0.30 | Jaccard similarity of interest sets |
| Wait time fairness | `W` | 0.0–1.0 | 0.20 | Longer wait → higher score (prevents starvation) |
| Recent match penalty | `R` | 0.0–1.0 | 0.10 | Penalize if recently matched with this user |

### Formula

```
Score = (wG × G) + (wA × A) + (wI × I) + (wW × W) + (wR × R)
```

Where `wG + wA + wI + wW + wR = 1.0`

### Variable Definitions

**Gender Compatibility (G):**
```
G = 1.0 if:
  - Requester has no preference (ANY), OR
  - Candidate's gender matches requester's preference,
  AND
  - Candidate has no preference (ANY), OR
  - Requester's gender matches candidate's preference
G = 0.0 otherwise
```

**Age Range Compatibility (A):**
```
A = 1.0 if:
  - Requester has no age preference, OR
  - Candidate's age range matches requester's preference
A = 0.0 otherwise
```

**Shared Interest Score (I):**
```
I = |requester_interests ∩ candidate_interests| / |requester_interests ∪ candidate_interests|
(Jaccard similarity coefficient)
If both have empty interest sets: I = 0.5 (neutral)
```

**Wait Time Fairness (W):**
```
W = min(candidate_wait_seconds / MAX_WAIT_SECONDS, 1.0)
MAX_WAIT_SECONDS = 300 (5 minutes)
```

**Recent Match Penalty (R):**
```
R = 1.0 if never previously matched
R = 0.3 if matched within last 24 hours
R = 0.0 if matched within last 1 hour
```

---

## Worked Examples

### Example 1: Perfect match

- Requester: female, age 25–34, interests: {music, travel}, waited 0s
- Candidate: male, age 25–34, interests: {music, travel, cooking}, waited 180s

```
G = 1.0 (both genders match each other's preferences — assume mutual)
A = 1.0 (age ranges match)
I = |{music, travel}| / |{music, travel, cooking}| = 2/3 = 0.667
W = 180/300 = 0.600
R = 1.0 (never matched before)

Score = (0.25 × 1.0) + (0.15 × 1.0) + (0.30 × 0.667) + (0.20 × 0.600) + (0.10 × 1.0)
     = 0.25 + 0.15 + 0.20 + 0.12 + 0.10
     = 0.82
```

### Example 2: No preferences set

- Requester: no gender, no age, interests: {}, waited 10s
- Candidate: no gender, no age, interests: {gaming}, waited 250s

```
G = 1.0 (no preferences = accept anyone)
A = 1.0 (no preferences)
I = 0.5 (requester has no interests — neutral)
W = 250/300 = 0.833
R = 1.0 (never matched)

Score = 0.25 + 0.15 + 0.15 + 0.167 + 0.10 = 0.817
```

### Example 3: Gender mismatch

- Requester: male, prefers female
- Candidate: male, prefers female

```
G = 0.0 (requester wants female, candidate is male)

Score will be low regardless of other factors.
```

---

## Preference Relaxation

### Decision: PROPOSED

If no candidates match hard preferences (gender, age) after a configurable timeout:

1. **0–60 seconds**: Strict matching (all preferences enforced)
2. **60–180 seconds**: Relax age preference (accept any age)
3. **180+ seconds**: Relax gender preference (accept any gender)

Relaxation is transparent to the user — they are told "We expanded your search to find a match faster."

**Open Question:** Should users be able to disable preference relaxation? Decision deferred to user feedback.

---

## Cold-Start Behavior

When few users are online:

| Scenario | Behavior |
|---|---|
| 0 candidates | User waits in queue; notified periodically |
| 1 candidate (but poor score) | Match anyway if score > 0.2 (minimum threshold) |
| Queue timeout (5 min) | "No match found. Try again later." |

### Minimum Score Threshold

- **0.2** — below this, do not match (prevents gender-mismatched forced pairing)
- Configurable via environment variable `MIN_MATCH_SCORE`

---

## Fairness & Bias

### Designed-In Protections

| Risk | Mitigation |
|---|---|
| Starvation (long-waiting users never matched) | Wait time is a positive scoring signal |
| Echo chamber (same interests always matched) | Interest weight is only 30%; other signals diversify |
| Gender bias | Symmetric compatibility check (both directions) |
| Discrimination by inferred traits | No trait inference; only explicit preferences used |
| Feedback loops | No model training on match outcomes in MVP |

### Prohibited Practices

1. Do not infer race, ethnicity, religion, disability, or sexual orientation
2. Do not use message content for matching
3. Do not rank users by "attractiveness" or "engagement score"
4. Do not create hidden quality tiers

---

## Anti-Abuse

| Abuse Pattern | Prevention |
|---|---|
| Rapid queue join/leave cycling | Rate limit: 10 match requests per 5 minutes |
| Queue manipulation (join, get info, leave) | Queue entry has no position visibility |
| Mass blocking to manipulate candidate pool | Block count monitored; excessive blocking flagged |

---

## Testing Requirements

### Unit Tests

- [ ] Score calculation with known inputs produces expected output
- [ ] Gender compatibility: all combinations tested
- [ ] Jaccard similarity: empty sets, identical sets, disjoint sets, partial overlap
- [ ] Wait time normalization: 0s, 150s, 300s, 600s (capped)
- [ ] Recent match penalty: never, 30min ago, 2h ago, 25h ago
- [ ] Minimum score threshold enforcement
- [ ] Self-matching excluded
- [ ] Blocked users excluded (both directions)

### Property-Based Tests

- [ ] Score is always in [0.0, 1.0]
- [ ] Symmetric compatibility: if A matches B, B's view of A is consistent
- [ ] No self-match in any random input

### Concurrency Tests

- [ ] Two users requesting simultaneously don't both match the same third user
- [ ] Atomic match creation with concurrent `/next` commands

---

## Related Documents

- [Data Flow](09-data-flow.md) — Matching sequence diagrams
- [State Machines](10-state-machines.md) — Queue state transitions
- [Performance & Concurrency](26-performance-and-concurrency.md) — Concurrent matching
- [AI & ML Strategy](17-ai-and-ml-strategy.md) — Future AI-enhanced matching
- [Privacy & Data Governance](19-privacy-and-data-governance.md) — Data used for matching
