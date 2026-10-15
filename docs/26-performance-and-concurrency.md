# 26 — Performance & Concurrency

## Purpose

Define the concurrency architecture, execution model, synchronization primitives, caching strategy, and performance budgets for LikBy under production constraints.

## Scope

Covers the asyncio runtime model, database contention management, Telegram webhook throughput, in-memory caching, and memory budget on resource-constrained environments (e.g., Render 512MB RAM).

---

## Concurrency Runtime Model

LikBy runs on Python 3.11+ using the standard `asyncio` event loop.

```mermaid
graph TD
    subgraph FastAPI / ASGI Worker (Single Process)
        EventLoop[asyncio Event Loop]
        
        subgraph Ingress
            WH[Telegram Webhook Ingress]
            Ack[Immediate HTTP 200 OK<br/>Latency < 25ms]
        end

        subgraph In-Memory Cache
            FastMap[Active Session Map<br/>user_id -> session_id + partner_id]
        end

        subgraph Background Task Queue
            TaskRelay[Message Relay Task]
            TaskMatch[Matchmaker Tick Task]
            TaskExpiry[Session Expiry Monitor]
        end

        subgraph IO Subsystems
            DB[(SQLite WAL / Postgres)]
            TGAPI[Telegram Bot API Client<br/>HTTP/2 via HTTPX / aiohttp]
        end
    end

    WH --> Ack
    WH --> FastMap
    FastMap --> TaskRelay
    TaskRelay --> TGAPI
    TaskMatch --> DB
    TaskExpiry --> DB
```

### Key Concurrency Rules

1. **Non-Blocking Ingress**: The FastAPI webhook route handler MUST return HTTP 200 within 50ms. If Telegram does not receive an acknowledgment within 5 seconds, it initiates aggressive exponential retries, creating request stampedes.
2. **Cooperative Multitasking**: Long-running or CPU-intensive operations (e.g., batch vector scoring) MUST be executed in an `asyncio.to_thread` executor to prevent starving the event loop.
3. **No Unbounded Tasks**: Background tasks spawned via `asyncio.create_task` are tracked in a set to prevent garbage collection and bound by an `asyncio.Semaphore` to cap concurrent Telegram dispatches.

---

## Active Session Memory Cache

Database round-trips for every relayed message add unnecessary latency (10-30ms per message). An in-memory concurrent cache provides sub-millisecond lookup for active chat sessions:

```python
# src/likby/services/session_cache.py
from dataclasses import dataclass
from typing import Optional, Dict
import asyncio

@dataclass(frozen=True)
class CachedSession:
    session_id: str
    user_a_id: str
    user_b_id: str
    user_a_tg_id: int
    user_b_tg_id: int

class ActiveSessionCache:
    """Thread-safe, sub-millisecond in-memory cache for active chat sessions."""

    def __init__(self) -> None:
        self._by_user_id: Dict[str, CachedSession] = {}
        self._by_tg_id: Dict[int, CachedSession] = {}
        self._lock = asyncio.Lock()

    async def put(self, session: CachedSession) -> None:
        async with self._lock:
            self._by_user_id[session.user_a_id] = session
            self._by_user_id[session.user_b_id] = session
            self._by_tg_id[session.user_a_tg_id] = session
            self._by_tg_id[session.user_b_tg_id] = session

    async def get_by_telegram_id(self, tg_id: int) -> Optional[CachedSession]:
        return self._by_tg_id.get(tg_id)

    async def remove(self, session_id: str) -> None:
        async with self._lock:
            to_remove = [k for k, v in self._by_tg_id.items() if v.session_id == session_id]
            for tg_id in to_remove:
                self._by_tg_id.pop(tg_id, None)
            to_remove_users = [k for k, v in self._by_user_id.items() if v.session_id == session_id]
            for uid in to_remove_users:
                self._by_user_id.pop(uid, None)
```

---

## SQLite Concurrency & Lock Contention

When running on SQLite in MVP:
- **Write Serialization**: SQLite permits only one active write transaction at a time.
- **WAL Mode**: Readers never block writers, and writers never block readers.
- **Busy Timeout**: Configured to `5000ms`. If another transaction holds the write lock, aiosqlite waits up to 5 seconds before raising `sqlite3.OperationalError: database is locked`.

### Best Practices Enforced
1. **Short Write Transactions**: Calculate scores, match combinations, and validate entities *before* acquiring the database transaction.
2. **Read-Only Connections**: Use separate connection instances for read-only queries where possible.
3. **Write Batching**: Periodic tasks (e.g., updating user `last_active_at`) are buffered in memory and flushed once every 60 seconds in a single batch transaction.

---

## Memory Budget & Resource Constraints

### Render Free Tier Profile
- **Memory Limit**: 512 MB RAM
- **CPU**: 0.1 CPU core shared
- **Inactivity Spin-down**: Spins down after 15 minutes of zero HTTP traffic.
- **Cold Start Penalty**: ~45 to 60 seconds to boot on subsequent requests.

### Target Memory Footprint

| Component | Target Baseline RAM | Peak Load RAM |
|---|---|---|
| Python Runtime + Modules (FastAPI, aiogram) | ~45 MB | ~50 MB |
| SQLite WAL In-Memory Cache | ~15 MB | ~25 MB |
| Active Session Cache (1,000 active sessions) | ~5 MB | ~12 MB |
| Webhook Request Buffers | ~10 MB | ~30 MB |
| Total Resident Set Size (RSS) | **~75 MB** | **~117 MB** |

The application uses less than 25% of the 512 MB limit, leaving over 380 MB headroom to prevent Out-Of-Memory (OOM) process termination.

---

## Latency Budgets & SLA Targets

| Operation | p50 Target | p95 Target | p99 Target | Max Acceptable |
|---|---|---|---|---|
| **Webhook Ingress Ack (HTTP 200)** | 12 ms | 35 ms | 70 ms | 200 ms |
| **Message Relay (End-to-End Delivery)** | 110 ms | 250 ms | 450 ms | 1,000 ms |
| **Match Enqueue** | 20 ms | 45 ms | 90 ms | 300 ms |
| **Match Execution (Candidate Pair)** | 35 ms | 80 ms | 150 ms | 500 ms |
| **Tic-Tac-Toe Move Validation & Update** | 80 ms | 180 ms | 350 ms | 800 ms |
| **Health Check (`/health`)** | 4 ms | 10 ms | 20 ms | 50 ms |
