# LikBy Release Quality Gates & CI Pipeline

---

## 1. Pre-Deployment Gates

Every release must pass all three automated quality gates:
1. **Gate 1 (Unit & Integration Tests):**
   ```bash
   python -m pytest tests/ -v
   ```
   *Requirement:* 100% pass rate (0 failures, 0 errors).
2. **Gate 2 (Linting & Style):**
   ```bash
   python -m ruff check src/ tests/
   ```
   *Requirement:* Zero lint violations.
3. **Gate 3 (Format Verification):**
   ```bash
   python -m ruff format --check src/ tests/
   ```
   *Requirement:* Zero format diffs.
