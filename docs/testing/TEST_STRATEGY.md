# LikBy Testing Strategy & Quality Assurance Architecture

**Current Test Status:** 116 / 116 Tests Passing (100% Pass Rate)  
**Execution Time:** ~22 seconds on standard dev hardware  
**Framework:** `pytest`, `pytest-asyncio`, `httpx`

---

## 1. Test Pyramid & Distribution

```
           /\
          /  \     E2E User Journeys (Integration) - ~15%
         /────\
        /      \    Subsystem Integration (API & DB) - ~25%
       /────────\
      /          \  Pure Unit Tests (Domain, Rules, Games) - ~60%
     /────────────\
```

- **Unit Tests (`tests/unit/`):** Pure Python business invariants, score calculation, 17 games logic, quota counters, referral reward caps, payment HMAC verification. Zero external network calls.
- **Integration Tests (`tests/integration/`):** SQLite persistence, FastAPI route responses, webhook signature checks, media quota event rollbacks.
