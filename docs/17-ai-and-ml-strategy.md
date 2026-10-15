# 17 — AI & ML Strategy

## Purpose

Evaluate AI use cases, define provider abstraction, establish mandatory rules, and separate justified AI from speculative features.

## Scope

Covers all proposed AI features and their implementation decision (implement now, defer, or reject).

---

## AI Use Case Evaluation

### UC-1: Conversation Icebreakers

| Aspect | Assessment |
|---|---|
| **User Problem** | Initial awkwardness when matched with a stranger |
| **Deterministic Baseline** | Curated list of icebreaker questions (implemented in MVP) |
| **ML Justified?** | Maybe — AI could personalize based on shared interests |
| **Data Requirements** | User interest tags only (NO message content) |
| **Privacy** | ✅ Safe — only sends interest tags to provider |
| **Provider Cost** | Low — one request per match (~100 tokens) |
| **Latency Budget** | 3 seconds (async; show deterministic fallback immediately) |
| **Failure Behavior** | Deterministic icebreaker from curated list |
| **Abuse Risk** | Low — output is a conversation prompt, not user-facing action |
| **Decision** | **DEFER to Phase 6** — deterministic baseline sufficient for MVP |

### UC-2: Interest & Topic Suggestions

| Aspect | Assessment |
|---|---|
| **User Problem** | Users with few selected interests have sparse profiles |
| **Deterministic Baseline** | Categorized interest catalog |
| **ML Justified?** | Low — categorized catalog is sufficient |
| **Decision** | **REJECT** — curated catalog is simpler and more predictable |

### UC-3: Message Toxicity/Spam Detection

| Aspect | Assessment |
|---|---|
| **User Problem** | Abusive messages harm victim experience |
| **Deterministic Baseline** | Rate limiting + user reporting + admin review |
| **ML Justified?** | Partially — but risks false positives and privacy invasion |
| **Data Requirements** | Would require sending message content to AI provider |
| **Privacy** | ❌ HIGH RISK — sends private conversation to third party |
| **Failure Behavior** | Deterministic controls remain active |
| **Abuse Risk** | Adversarial evasion; false positives on cultural differences |
| **Decision** | **DEFER** — MVP uses deterministic controls. Revisit only with clear consent framework and on-device/on-premise model options |

### UC-4: Language Assistance

| Aspect | Assessment |
|---|---|
| **User Problem** | Language barriers between matched users |
| **Deterministic Baseline** | Language preference matching |
| **ML Justified?** | Translation could help, but adds complexity and latency |
| **Privacy** | ❌ HIGH RISK — sends message content for translation |
| **Decision** | **DEFER** — language preference matching is sufficient for MVP |

### UC-5: Semantic Interest Similarity

| Aspect | Assessment |
|---|---|
| **User Problem** | "Music" and "Guitar" should score similarly |
| **Deterministic Baseline** | Exact interest tag matching (Jaccard) |
| **ML Justified?** | Yes — embeddings can capture semantic similarity |
| **Data Requirements** | Interest tags only (pre-computed embeddings) |
| **Privacy** | ✅ Safe — interest catalog, not user content |
| **Cost** | One-time embedding computation; stored locally |
| **Decision** | **DEFER to Phase 6** — exact matching is acceptable for MVP |

### UC-6: Matching Explanations

| Aspect | Assessment |
|---|---|
| **User Problem** | Users wonder "why was I matched with this person?" |
| **Deterministic Baseline** | Template: "You were matched based on shared interest in {X}" |
| **ML Justified?** | No — template + scoring data is sufficient |
| **Decision** | **REJECT** — deterministic templates are clearer and more trustworthy |

### UC-7: Moderation Triage & Prioritization

| Aspect | Assessment |
|---|---|
| **User Problem** | Admin overwhelmed with reports |
| **Deterministic Baseline** | Category-based priority (suspected_minor > harassment > spam) |
| **ML Justified?** | Maybe — could prioritize within categories |
| **Data Requirements** | Report text and category |
| **Privacy** | Medium — report descriptions may contain sensitive content |
| **Decision** | **DEFER** — deterministic priority ordering is sufficient until report volume justifies AI |

---

## Decision Summary

| Use Case | Decision | Phase |
|---|---|---|
| Icebreakers | DEFER | Phase 6 |
| Topic suggestions | REJECT | — |
| Toxicity detection | DEFER | Post-Phase 6 |
| Language assistance | DEFER | Post-Phase 6 |
| Semantic interest similarity | DEFER | Phase 6 |
| Matching explanations | REJECT | — |
| Moderation triage | DEFER | Post-Phase 6 |

---

## Provider Abstraction

### Design: DECIDED

```python
from abc import ABC, abstractmethod

class AIProvider(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str, max_tokens: int = 100) -> str | None: ...

    @abstractmethod
    async def get_embedding(self, text: str) -> list[float] | None: ...

class NoOpProvider(AIProvider):
    """Fallback provider that always returns None."""
    async def generate_text(self, prompt: str, max_tokens: int = 100) -> str | None:
        return None

    async def get_embedding(self, text: str) -> list[float] | None:
        return None

class GeminiProvider(AIProvider):
    """Google Gemini API provider (future)."""
    ...
```

### Provider Configuration

```python
class AIConfig(BaseSettings):
    ai_enabled: bool = False
    ai_provider: str = "noop"  # "noop", "gemini", etc.
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: int = 5
    ai_max_retries: int = 2
    ai_daily_quota: int = 1000
    ai_max_tokens_per_request: int = 200
```

---

## Mandatory AI Rules

1. ✅ Basic chat and matching work without AI provider
2. ✅ Never send private message content to external AI without clear consent
3. ✅ Prefer metadata/interests over conversation surveillance
4. ✅ Do not train on private messages
5. ✅ AI cannot execute privileged actions
6. ✅ Validate AI output with Pydantic schemas
7. ✅ Use timeouts, bounded retries, quotas, cost controls
8. ✅ Never trust AI as authorization decision
9. ✅ Do not infer protected attributes
10. ✅ Do not auto-ban based on AI classifier scores
11. ✅ Deterministic fallbacks for provider failure
12. ✅ Prompts and model settings are configurable
13. ✅ No paid API required for startup

---

## Terminology Clarity

| Term | What It Means in Tikible |
|---|---|
| **Rules-based** | Hand-written if/else logic, scoring formulas, curated lists |
| **Traditional ML** | Trained models (embeddings, classifiers) — not used in MVP |
| **LLM** | Large language model API (Gemini, etc.) — optional, deferred |

The MVP matching engine is **rules-based**, not ML. Do not claim it uses AI or machine learning.

---

## Related Documents

- [Matching Engine](14-matching-engine.md)
- [Chat Session Lifecycle](15-chat-session-lifecycle.md)
- [Privacy & Data Governance](19-privacy-and-data-governance.md)
- [Security Threat Model](18-security-threat-model.md)
- [Configuration & Secrets](31-configuration-and-secrets.md)
