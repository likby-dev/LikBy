# ==============================================================================
# LikBy Production Dockerfile
# Multi-stage, distroless-lean, non-root security hardened, PID-1 signal-aware
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build & Dependency Compilation Stage
# ------------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

# Prevent Python from writing .pyc files & enable unbuffered stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install minimal build tools required for compiling C-extensions / binary wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create isolated Python virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install wheel & pip upgrades
RUN pip install --upgrade pip setuptools wheel

# Install production dependencies first (layer-cached until requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy package configuration and source for editable/wheel install
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps -e .


# ------------------------------------------------------------------------------
# Stage 2: Minimal Hardened Production Runtime Stage
# ------------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runner

# Security: Metadata labels (OCI compliant)
LABEL org.opencontainers.image.title="LikBy Platform API" \
      org.opencontainers.image.description="LikBy Production FastAPI & Telegram Engine" \
      org.opencontainers.image.vendor="LikBy" \
      org.opencontainers.image.licenses="Proprietary"

# Environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    ENVIRONMENT=production \
    PATH="/opt/venv/bin:$PATH"

# Install only essential runtime dependencies (curl for container health probes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create unprivileged system group & user (UID/GID 10001 for least-privilege security)
RUN groupadd -g 10001 likby && \
    useradd -u 10001 -g likby -m -d /home/likby -s /usr/sbin/nologin likby

WORKDIR /app

# Copy virtualenv and package from builder
COPY --from=builder --chown=likby:likby /opt/venv /opt/venv
COPY --from=builder --chown=likby:likby /build/src /app/src
COPY --from=builder --chown=likby:likby /build/pyproject.toml /app/pyproject.toml

# Set non-root user permissions
RUN chown -R likby:likby /app /home/likby

# Switch to non-root execution
USER likby

# Expose default application port
EXPOSE 8000

# Container healthcheck targeting liveness endpoint
HEALTHCHECK --interval=20s --timeout=4s --start-period=8s --retries=3 \
  CMD curl -f http://127.0.0.1:${PORT:-8000}/health/live || exit 1

# Launch FastAPI via Uvicorn with dynamic port binding, proxy header resolution, and exec signal handling
CMD ["sh", "-c", "exec uvicorn likby.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]

