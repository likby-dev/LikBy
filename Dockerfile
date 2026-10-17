# Production Dockerfile for LikBy on Render / Container Environments
FROM python:3.11-slim

# Prevent python from buffering stdout/stderr and generating .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install system utilities (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies manifest and install
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy source and packaging definitions
COPY pyproject.toml .
COPY src/ ./src/

# Install the likby package in editable mode without reinstalling dependencies
RUN pip install --no-deps -e .

# Expose HTTP port (Render sets $PORT dynamically)
EXPOSE 8000

# Container healthcheck hitting FastAPI liveness endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health/live || exit 1

# Default execution: run the Webhook FastAPI server
CMD ["python", "-m", "likby.main", "--mode", "webhook"]
