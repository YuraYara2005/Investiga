# ==============================================================================
# Investiga Backend – Dockerfile
# ==============================================================================
# Build context: repository root  (docker compose build context: .)
# This file lives at: docker/backend/Dockerfile
# ==============================================================================

FROM python:3.12-slim

# ---------------------------------------------------------------------------- #
# OS-level dependencies
# curl  – used by the HEALTHCHECK and entrypoint Qdrant wait loop
# ---------------------------------------------------------------------------- #
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl \
       netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------- #
# Non-root application user
# ---------------------------------------------------------------------------- #
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --no-create-home --shell /sbin/nologin appuser

# ---------------------------------------------------------------------------- #
# Working directory inside the container
# All paths relative to /app match the layout expected by Alembic and uvicorn.
# ---------------------------------------------------------------------------- #
WORKDIR /app

# ---------------------------------------------------------------------------- #
# Install Python dependencies (separate layer for cache efficiency)
# ---------------------------------------------------------------------------- #
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------- #
# Copy backend source (app/, alembic.ini, pyproject.toml)
# ---------------------------------------------------------------------------- #
COPY backend/ ./

# ---------------------------------------------------------------------------- #
# Copy Docker entrypoint scripts (relative to build context = repo root)
# ---------------------------------------------------------------------------- #
COPY docker/backend/entrypoint.sh /docker-entrypoint.sh
COPY docker/backend/wait_for_db.py /wait_for_db.py
RUN chmod +x /docker-entrypoint.sh

# ---------------------------------------------------------------------------- #
# Ownership handover to non-root user
# ---------------------------------------------------------------------------- #
RUN chown -R appuser:appgroup /app /docker-entrypoint.sh /wait_for_db.py

USER appuser

# ---------------------------------------------------------------------------- #
# Runtime configuration
# ---------------------------------------------------------------------------- #
EXPOSE 8000

# Liveness probe – lightweight, never checks external deps
HEALTHCHECK --interval=15s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8000/health/live || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
