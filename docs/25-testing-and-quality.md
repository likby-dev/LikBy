# 25 — Testing & Quality

## Purpose

Define the comprehensive testing strategy, quality gates, test hierarchy, mocking guidelines, and automated verification procedures for LikBy.

## Scope

Covers unit, integration, contract, security, load, and end-to-end testing across all application modules.

---

## Testing Pyramid & Quality Targets

```
           / \
          /   \     E2E / Telegram Scenario Tests (5%)
         /=====\
        /       \   Integration & Database Tests (25%)
       /=========\
      /           \ Unit & Domain Logic Tests (70%)
     /-------------\
```

### Coverage & Gate Metrics

| Test Layer | Target Coverage | Enforcement | Scope |
|---|---|---|---|
| **Domain Logic (`likby.domain`)** | **≥ 95%** | Hard CI Gate | Pure business logic, state machines, matching engine, game rules |
| **Application Services (`likby.services`)** | **≥ 90%** | Hard CI Gate | Session lifecycle, user coordination, rate limiting |
| **Repositories (`likby.repositories`)** | **≥ 85%** | Hard CI Gate | SQLite & PostgreSQL query execution, schema constraints |
| **Telegram Adapter (`likby.telegram`)** | **≥ 80%** | Hard CI Gate | Handler routing, keyboard generation, update parsing |
| **Overall Project** | **≥ 88%** | Hard CI Gate | Entire codebase |

---

## Tooling & Architecture

- **Test Runner**: `pytest` with `pytest-asyncio` (`asyncio_mode = "auto"`)
- **Coverage**: `pytest-cov` generating terminal summaries and XML reports
- **Linter / Formatter**: `ruff` (replaces Black, Flake8, isort)
- **Type Checker**: `mypy --strict`
- **Security Scanner**: `bandit` and `pip-audit`

```ini
# pyproject.toml configuration excerpt
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "--strict-markers --cov=src/likby --cov-report=term-missing --cov-fail-under=85"

[tool.mypy]
strict = true
python_version = "3.11"
disallow_untyped_defs = true
warn_unused_ignores = true
plugins = ["pydantic.mypy"]
```

---

## Fixtures & Test Scaffolding (`tests/conftest.py`)

```python
# tests/conftest.py
import pytest
import aiosqlite
from typing import AsyncGenerator
from unittest.mock import AsyncMock
from aiogram import Bot
from likby.domain.entities.user import User, UserState, UserStatus
from likby.domain.entities.profile import Profile
from likby.repositories.sqlite.database import init_sqlite_schema

@pytest.fixture
async def sqlite_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """In-memory SQLite connection with complete test schema."""
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys = ON;")
    await init_sqlite_schema(conn)
    yield conn
    await conn.close()

@pytest.fixture
def mock_bot() -> AsyncMock:
    """Mock aiogram Bot instance preventing external Telegram API calls."""
    bot = AsyncMock(spec=Bot)
    bot.send_message.return_value = AsyncMock(message_id=101)
    bot.edit_message_text.return_value = AsyncMock(message_id=101)
    bot.delete_message.return_value = True
    return bot

@pytest.fixture
def sample_user_a() -> User:
    return User(
        id="usr_001",
        telegram_id=111111,
        state=UserState.ACTIVE,
        status=UserStatus.ACTIVE,
        age_verified=True,
    )

@pytest.fixture
def sample_profile_a() -> Profile:
    return Profile(
        user_id="usr_001",
        display_name="UserA",
        age=24,
        gender="MALE",
        languages=["en"],
        interests=["coding", "gaming"],
        preferred_gender_filter=["ANY"],
        min_age_filter=20,
        max_age_filter=30,
    )
```

---

## Critical Test Suites

### 1. Matching Engine Scoring & Determinism

Verifies compatibility calculations, zero-division boundaries, and reciprocal preference filtering.

```python
# tests/unit/test_matching_engine.py
import pytest
from likby.domain.matching.scorer import calculate_match_score

def test_reciprocal_gender_mismatch_yields_zero():
    # User A wants FEMALE only; User B is MALE
    score = calculate_match_score(
        user_a_gender="MALE",
        user_a_pref=["FEMALE"],
        user_a_age=25,
        user_a_age_range=(20, 30),
        user_b_gender="MALE",
        user_b_pref=["ANY"],
        user_b_age=26,
        user_b_age_range=(20, 30),
        common_interests=["gaming"],
        common_languages=["en"]
    )
    assert score == 0.0

def test_compatible_users_score_above_threshold():
    score = calculate_match_score(
        user_a_gender="NON_BINARY",
        user_a_pref=["ANY"],
        user_a_age=25,
        user_a_age_range=(20, 30),
        user_b_gender="FEMALE",
        user_b_pref=["ANY"],
        user_b_age=24,
        user_b_age_range=(22, 28),
        common_interests=["coffee", "books"],
        common_languages=["en"]
    )
    assert score > 0.6
```

### 2. Privacy Test: Message Text Never Persisted

Guarantees by architectural design that message payloads cannot leak to persistence.

```python
# tests/integration/test_privacy_guarantees.py
import pytest
from likby.services.chat_service import ChatRelayService

async def test_relayed_messages_do_not_persist_content(sqlite_db, mock_bot):
    service = ChatRelayService(db=sqlite_db, bot=mock_bot)
    
    # Send confidential text through relay
    await service.relay_text(
        session_id="ses_test",
        sender_id="usr_001",
        recipient_telegram_id=222222,
        text="SUPER_SECRET_PAYLOAD_12345"
    )

    # Inspect all database tables to verify zero presence of the string
    async with sqlite_db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
        tables = [row[0] for row in await cursor.fetchall()]

    for table in tables:
        async with sqlite_db.execute(f"SELECT * FROM {table}") as cur:
            rows = await cur.fetchall()
            dumped_content = str(rows)
            assert "SUPER_SECRET_PAYLOAD_12345" not in dumped_content, (
                f"Privacy violation! Secret payload detected in table: {table}"
            )
```

### 3. Server-Authoritative Game State Validation

Verifies invalid moves, out-of-turn attempts, and winning conditions for Tic-Tac-Toe.

```python
# tests/unit/test_tictactoe_engine.py
import pytest
from likby.games.tictactoe import TicTacToeGame, InvalidMoveError, NotYourTurnError

def test_out_of_turn_move_rejected():
    game = TicTacToeGame.create(player_x="usr_001", player_o="usr_002")
    # Player O attempts first move instead of X
    with pytest.raises(NotYourTurnError):
        game.make_move(player_id="usr_002", row=0, col=0)

def test_occupied_cell_move_rejected():
    game = TicTacToeGame.create(player_x="usr_001", player_o="usr_002")
    game.make_move(player_id="usr_001", row=1, col=1)
    with pytest.raises(InvalidMoveError):
        game.make_move(player_id="usr_002", row=1, col=1)
```

---

## Load & Stress Testing

Load tests are written with **Locust** simulating concurrent Telegram webhook updates:
- **Target Target**: 500 concurrent active users.
- **Queue Saturation**: 100 users enqueueing simultaneously.
- **Relay Latency**: p95 delivery < 150ms; p99 < 400ms.
- **Zero Lock Hangs**: Verify zero SQLite `busy_timeout` exceptions during peak concurrent read/write transactions.
