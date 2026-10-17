# Contributing to LikBy

Thank you for your interest in contributing to **LikBy** (*Meet. Connect. Play.*). This document sets the guidelines for developers, architects, and QA engineers working on this repository.

---

## 1. Code of Conduct & Core Principles

LikBy is built on respect, safety, privacy, and technical excellence:
- **Privacy-First:** User data belongs to the user. We enforce strict data isolation, zero advertising, and persistent chat retention without ephemeral destruction.
- **Safety & Content Protection:** All shared media via Telegram uses `protect_content=True`. All abuse reports are recorded and actionable.
- **Craftsmanship:** Write modular, testable, fully type-annotated Python code following Clean Architecture principles.

---

## 2. Development Setup

### Prerequisites
- Python 3.11 or higher (Python 3.12 / 3.13 recommended)
- Git
- Virtual environment (`venv` or `conda`)

### Local Setup Steps
1. **Clone the repository:**
   ```bash
   git clone https://github.com/likby-dev/LikBy.git
   cd LikBy
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-asyncio httpx ruff
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   For local development, no third-party cloud keys are required. The default configuration uses SQLite and local file storage:
   ```env
   APP_ENV=development
   STORAGE_BACKEND=local
   TELEGRAM_MODE=polling
   TELEGRAM_BOT_TOKEN=123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ
   DATABASE_URL=sqlite+aiosqlite:///likby.db
   ```

---

## 3. Running the Application

### Start the FastAPI Server with Bot:
```bash
python -m likby.main
```
Or with Uvicorn directly:
```bash
uvicorn likby.main:app --host 0.0.0.0 --port 8000 --reload
```

### Health Check Endpoints:
- `http://localhost:8000/` -> Root status & service info
- `http://localhost:8000/health/live` -> Liveness probe
- `http://localhost:8000/health/ready` -> Readiness probe
- `http://localhost:8000/docs` -> Interactive OpenAPI documentation

---

## 4. Branching & Commit Workflow

- **Branch naming convention:**
  - `feature/<short-description>` (e.g., `feature/game-audio-sync`)
  - `fix/<short-description>` (e.g., `fix/quota-rollback-edgecase`)
  - `docs/<short-description>` (e.g., `docs/add-api-contracts`)
  - `refactor/<short-description>`
- **Commit messages:**
  - Use conventional commits format: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
  - Example: `feat(games): add server-side validation for stick arena KO conditions`

---

## 5. Testing & Quality Standards

Before opening a pull request or submitting code:
1. **Run all tests:**
   ```bash
   python -m pytest tests/ -v
   ```
   All 116+ tests must pass.
2. **Run linting and formatting:**
   ```bash
   python -m ruff check src/ tests/
   python -m ruff format --check src/ tests/
   ```
3. **Write tests for new features:** Every new use case, game rule, or payment handler must be accompanied by comprehensive unit and integration tests.

---

## 6. Architecture & Subsystem Boundaries

- **`src/likby/domain/`**: Pure business models and logic (no external dependencies).
- **`src/likby/services/`**: Application services and use cases (quotas, matchmaking, payments).
- **`src/likby/repositories/`**: Storage interfaces and concrete adapters (SQLite, Supabase, Firestore).
- **`src/likby/telegram/`**: Telegram bot handlers, keyboards, middlewares, and callbacks.
- **`src/likby/api/`**: FastAPI REST routers and webhook receivers.
- **`src/likby/games/`**: Server-authoritative game rule engines and session registries.

---

## 7. Reporting Issues

Please file issues in the repository tracker using the provided issue templates. For security vulnerabilities, refer to [SECURITY.md](SECURITY.md).
