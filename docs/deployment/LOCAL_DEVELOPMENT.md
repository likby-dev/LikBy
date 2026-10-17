# LikBy Local Development Guide

---

## 1. Quick Start (Zero Cloud Credentials Required)

```bash
# 1. Clone repository & enter directory
git clone https://github.com/likby-dev/LikBy.git
cd LikBy

# 2. Setup Python environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows

# 3. Install dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx ruff

# 4. Prepare local environment
cp .env.example .env

# 5. Launch FastAPI application and bot in polling mode
python -m likby.main
```

The application initializes `likby.db` automatically in SQLite WAL mode.
