# 06 — Module Boundaries

## Purpose

Define explicit boundaries, contracts, and dependency rules between internal modules. Prevent circular dependencies and ensure each module can be tested independently.

## Scope

Covers all modules in the `src/tikible/` package.

---

## Module Ownership Matrix

| Module | Owns | Depends On | Never Depends On |
|---|---|---|---|
| `config` | Application settings | `pydantic-settings` | Any other internal module |
| `domain/entities` | Entity definitions, value objects | Nothing | Services, repositories, telegram |
| `domain/matching` | Matching algorithm, scoring | `domain/entities` | Services, storage, telegram |
| `domain/games/` | Game rules, board logic | `domain/entities` | Services, storage, telegram |
| `domain/rate_limiting` | Rate limit logic | `domain/entities` | Services, storage |
| `domain/exceptions` | Domain error types | Nothing | Everything else |
| `repositories/interfaces` | Storage contracts (ABCs) | `domain/entities` | Storage implementations |
| `repositories/sqlite/` | SQLite storage | `repositories/interfaces`, `domain/entities` | Services, telegram |
| `repositories/memory/` | In-memory storage (testing) | `repositories/interfaces`, `domain/entities` | Services, telegram |
| `services/` | Application orchestration | `domain/`, `repositories/interfaces` | `telegram/`, `api/`, storage implementations |
| `telegram/` | Telegram interaction | `services/`, `domain/entities` | `repositories/`, `api/` |
| `api/` | HTTP endpoints | `services/`, `domain/entities` | `telegram/`, `repositories/` |
| `security/` | Auth, redaction | `config` | `services/`, `domain/` (except for middleware use) |
| `observability/` | Logging, health checks | `config` | `services/`, `domain/` |

---

## Dependency Rules

### Rule 1: Inner layers never import outer layers

```
domain/ ← services/ ← telegram/
domain/ ← services/ ← api/
repositories/interfaces ← repositories/sqlite/
```

**Violation example** (FORBIDDEN):
```python
# In domain/matching.py — WRONG
from tikible.services.user_service import UserService  # ❌ Domain importing service
```

### Rule 2: Telegram adapter never accesses storage

```python
# In telegram/handlers/match.py — WRONG
from tikible.repositories.sqlite.user_repo import SQLiteUserRepo  # ❌

# CORRECT
from tikible.services.matching_service import MatchingService  # ✅
```

### Rule 3: Services use repository interfaces, not implementations

```python
# In services/user_service.py — WRONG
from tikible.repositories.sqlite.user_repo import SQLiteUserRepo  # ❌

# CORRECT
from tikible.repositories.interfaces import UserRepository  # ✅
```

### Rule 4: Domain has no framework dependencies

The `domain/` package must not import FastAPI, aiogram, aiosqlite, or HTTPX. Only Python standard library and Pydantic (for data modeling).

---

## Module Contracts

### UserRepository (Interface)

```python
class UserRepository(ABC):
    async def create(self, user: User) -> User: ...
    async def get_by_id(self, user_id: str) -> User | None: ...
    async def get_by_telegram_id(self, telegram_id: int) -> User | None: ...
    async def update(self, user: User) -> User: ...
    async def delete(self, user_id: str) -> None: ...
    async def exists(self, user_id: str) -> bool: ...
```

### SessionRepository (Interface)

```python
class SessionRepository(ABC):
    async def create(self, session: ChatSession) -> ChatSession: ...
    async def get_active_by_user(self, user_id: str) -> ChatSession | None: ...
    async def get_by_id(self, session_id: str) -> ChatSession | None: ...
    async def update_status(self, session_id: str, status: SessionStatus) -> None: ...
    async def end_session(self, session_id: str) -> None: ...
```

### MatchQueueRepository (Interface)

```python
class MatchQueueRepository(ABC):
    async def enqueue(self, entry: QueueEntry) -> None: ...
    async def dequeue(self, user_id: str) -> None: ...
    async def find_candidates(self, for_user: User, exclude: set[str]) -> list[QueueEntry]: ...
    async def is_queued(self, user_id: str) -> bool: ...
    async def expire_stale(self, max_age_seconds: int) -> int: ...
```

### BlockRepository (Interface)

```python
class BlockRepository(ABC):
    async def block(self, blocker_id: str, blocked_id: str) -> None: ...
    async def unblock(self, blocker_id: str, blocked_id: str) -> None: ...
    async def is_blocked(self, user_a: str, user_b: str) -> bool: ...
    async def get_blocked_by(self, user_id: str) -> set[str]: ...
```

### GameRepository (Interface)

```python
class GameRepository(ABC):
    async def create(self, game: GameSession) -> GameSession: ...
    async def get_by_id(self, game_id: str) -> GameSession | None: ...
    async def get_active_by_session(self, session_id: str) -> GameSession | None: ...
    async def update_state(self, game_id: str, state: GameState) -> None: ...
    async def end_game(self, game_id: str, result: GameResult) -> None: ...
```

---

## Inter-Module Communication

### Services → Domain

Services call domain functions directly. Domain functions are pure or near-pure, operating on entities and returning results.

```python
# In services/matching_service.py
from tikible.domain.matching import find_best_match, calculate_score

async def find_match(self, user: User) -> MatchResult:
    candidates = await self.queue_repo.find_candidates(user, blocked)
    scored = [calculate_score(user, c) for c in candidates]
    return find_best_match(scored)
```

### Services → Repository

Services receive repository instances via dependency injection (constructor injection at startup).

```python
class MatchingService:
    def __init__(self, user_repo: UserRepository, queue_repo: MatchQueueRepository,
                 session_repo: SessionRepository, block_repo: BlockRepository):
        self._user_repo = user_repo
        self._queue_repo = queue_repo
        self._session_repo = session_repo
        self._block_repo = block_repo
```

### Telegram → Services

Telegram handlers receive service instances from aiogram's dependency injection or middleware.

```python
# In telegram/handlers/match.py
async def handle_find_match(message: Message, matching_service: MatchingService):
    result = await matching_service.join_queue(user_id=str(message.from_user.id))
    # Format and send response
```

---

## Testing Boundaries

| Module | Test Type | Dependencies |
|---|---|---|
| `domain/` | Unit tests | None — pure logic |
| `domain/games/` | Unit tests | None — deterministic rules |
| `services/` | Unit tests with mock repositories | `repositories/memory/` or mocks |
| `repositories/sqlite/` | Integration tests | SQLite in-memory database |
| `telegram/` | Handler tests with mock services | Mock services, aiogram test utilities |
| `api/` | API tests | HTTPX test client, mock services |

---

## Related Documents

- [High-Level Architecture](05-high-level-architecture.md)
- [Domain Model](07-domain-model.md)
- [Storage & Persistence](20-storage-and-persistence.md)
- [Testing & Quality](25-testing-and-quality.md)
