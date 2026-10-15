# LikBy

**Privacy-first anonymous social matching and real-time chat platform.**

LikBy helps adults discover compatible people, communicate anonymously, and build meaningful conversations through a simple, enjoyable, safe, and privacy-respecting experience.

> [!IMPORTANT]
> This project is in the **architecture and documentation** phase. No production features are implemented yet. The documentation in `docs/` is the engineering source of truth.

---

## Quick Links

| Document | Purpose |
|---|---|
| [Executive Summary](docs/00-executive-summary.md) | High-level overview and key decisions |
| [Product Requirements](docs/01-product-requirements.md) | Feature inventory and MVP scope |
| [Scope & Roadmap](docs/02-scope-and-roadmap.md) | Phased implementation plan |
| [Research & Assumptions](docs/03-research-and-assumptions.md) | Verified facts, sources, and open questions |
| [System Context](docs/04-system-context.md) | External systems and boundaries |
| [High-Level Architecture](docs/05-high-level-architecture.md) | Layered architecture and module overview |
| [Module Boundaries](docs/06-module-boundaries.md) | Internal module contracts and dependencies |
| [Domain Model](docs/07-domain-model.md) | Core entities and business rules |
| [Entity Relationships](docs/08-entity-relationships.md) | ER diagrams and relationship matrix |
| [Data Flow](docs/09-data-flow.md) | Sequence diagrams for all major flows |
| [State Machines](docs/10-state-machines.md) | State transition diagrams and rules |
| [Telegram Bot Design](docs/11-telegram-bot-design.md) | Bot commands, keyboards, and UX |
| [API Contracts](docs/12-api-contracts.md) | Internal API design and schemas |
| [Auth & Authorization](docs/13-authentication-and-authorization.md) | Security boundaries and access control |
| [Matching Engine](docs/14-matching-engine.md) | Algorithm, scoring, and fairness |
| [Chat Session Lifecycle](docs/15-chat-session-lifecycle.md) | Session creation, relay, and teardown |
| [Multiplayer Games](docs/16-multiplayer-games.md) | Game architecture and MVP game |
| [AI & ML Strategy](docs/17-ai-and-ml-strategy.md) | Optional AI features and provider design |
| [Security Threat Model](docs/18-security-threat-model.md) | STRIDE analysis and controls |
| [Privacy & Data Governance](docs/19-privacy-and-data-governance.md) | Data classification, retention, deletion |
| [Storage & Persistence](docs/20-storage-and-persistence.md) | SQLite design, repository interfaces |
| [Supabase Architecture](docs/21-supabase-architecture.md) | Future PostgreSQL migration |
| [Firestore Architecture](docs/22-firestore-architecture.md) | Future document-store adapter |
| [Data Migration Runbook](docs/23-data-migration-runbook.md) | Migration procedures and validation |
| [UI/UX & Conversation Design](docs/24-ui-ux-and-conversation-design.md) | Message copy, flows, and design system |
| [Testing & Quality](docs/25-testing-and-quality.md) | Test strategy and coverage targets |
| [Performance & Concurrency](docs/26-performance-and-concurrency.md) | Concurrency model and optimization |
| [Observability & Operations](docs/27-observability-and-operations.md) | Logging, metrics, and monitoring |
| [Render Deployment](docs/28-render-deployment.md) | Deployment configuration and constraints |
| [Free-Tier & Cost Model](docs/29-free-tier-and-cost-model.md) | Cost analysis and upgrade triggers |
| [CI/CD & Release Process](docs/30-ci-cd-and-release-process.md) | GitHub Actions and release workflow |
| [Configuration & Secrets](docs/31-configuration-and-secrets.md) | Environment variables and secret management |
| [Backup & Recovery](docs/32-backup-and-recovery.md) | Data protection and recovery procedures |
| [Incident Response](docs/33-incident-response.md) | Incident handling and escalation |
| [Web & Mini App Future](docs/34-web-and-mini-app-future.md) | Future client integration |
| [Implementation Roadmap](docs/35-implementation-roadmap.md) | Dependency-ordered build plan |
| [Acceptance Criteria](docs/36-acceptance-criteria.md) | Definition of done for each phase |
| [Risk Register](docs/37-risk-register.md) | Identified risks and mitigations |
| [Glossary](docs/38-glossary.md) | Terminology and definitions |
| [Architecture Decisions](docs/39-architecture-decisions.md) | ADR log |
| [Troubleshooting](docs/40-troubleshooting.md) | Common issues and solutions |

---

## Technology Stack

| Layer | Technology | Version Constraint |
|---|---|---|
| Language | Python | ≥ 3.11 |
| Telegram | aiogram | 3.x (pinned) |
| Backend/API | FastAPI | ≥ 0.126.0 |
| Validation | Pydantic | ≥ 2.7.0 |
| ASGI Server | Uvicorn | latest stable |
| HTTP Client | HTTPX | latest stable |
| Local Storage | SQLite (aiosqlite) | built-in + WAL mode |
| Testing | pytest, pytest-asyncio | latest stable |
| Code Quality | Ruff, mypy | latest stable |
| Deployment | Render | Free tier (documented limitations) |

---

## Project Structure (Planned)

```
likby/
├── src/
│   └── likby/
│       ├── __init__.py
│       ├── main.py              # FastAPI app entry
│       ├── config.py            # Typed settings
│       ├── domain/              # Entities, value objects, rules
│       ├── services/            # Application services
│       ├── repositories/        # Storage interfaces + adapters
│       ├── telegram/            # aiogram adapter
│       ├── api/                 # FastAPI routes
│       ├── games/               # Game engine modules
│       ├── ai/                  # AI provider abstractions
│       ├── security/            # Auth, rate limiting, validation
│       └── observability/       # Logging, health checks
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── docs/                        # Architecture documentation
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Development Setup

```powershell
# Clone the repository
git clone <repository-url>
cd likby

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies (when available)
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env with your BOT_TOKEN

# Run tests
pytest

# Start development server (long polling mode)
python -m likby.main --mode polling
```

---

## License

To be determined.

## Contributing

Architecture documentation must be reviewed and approved before implementation begins. See [Implementation Roadmap](docs/35-implementation-roadmap.md) for the current phase.
