#!/usr/bin/env sh
# ==============================================================================
# Investiga Backend – Container Entrypoint
# ==============================================================================
# Execution order:
#   1. Wait for PostgreSQL to accept TCP connections
#   2. Wait for Qdrant REST API to respond
#   3. Run Alembic database migrations
#   4. Start Uvicorn ASGI server
# ==============================================================================
set -e

# ---------------------------------------------------------------------------- #
# Colour helpers (safe for non-TTY)
# ---------------------------------------------------------------------------- #
log_info()  { printf '\033[0;34m[INFO ]\033[0m  %s\n' "$*"; }
log_ok()    { printf '\033[0;32m[ OK  ]\033[0m  %s\n' "$*"; }
log_error() { printf '\033[0;31m[ERROR]\033[0m  %s\n' "$*" >&2; }

# ---------------------------------------------------------------------------- #
# 1. Wait for PostgreSQL
# ---------------------------------------------------------------------------- #
log_info "Waiting for PostgreSQL to become ready..."
python /wait_for_db.py
log_ok "PostgreSQL is accepting connections."

# ---------------------------------------------------------------------------- #
# 2. Wait for Qdrant REST endpoint
# ---------------------------------------------------------------------------- #
QDRANT_HOST="${VECTORSTORE__HOST:-qdrant}"
QDRANT_PORT="${VECTORSTORE__PORT:-6333}"
QDRANT_URL="http://${QDRANT_HOST}:${QDRANT_PORT}/readyz"
QDRANT_RETRIES=30
QDRANT_WAIT=2

log_info "Waiting for Qdrant at ${QDRANT_URL}..."
i=0
until curl -sf "${QDRANT_URL}" > /dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge "$QDRANT_RETRIES" ]; then
        log_error "Qdrant did not become ready after $((QDRANT_RETRIES * QDRANT_WAIT))s. Aborting."
        exit 1
    fi
    printf '.'
    sleep "${QDRANT_WAIT}"
done
printf '\n'
log_ok "Qdrant is ready."

# ---------------------------------------------------------------------------- #
# 3. Run Alembic migrations
# ---------------------------------------------------------------------------- #
log_info "Running Alembic database migrations..."
alembic upgrade head
log_ok "Migrations applied successfully."

# ---------------------------------------------------------------------------- #
# 4. Start Uvicorn
# ---------------------------------------------------------------------------- #
log_info "Starting Investiga backend (uvicorn)..."
exec uvicorn app.main:app \
    --host "${SERVER__HOST:-0.0.0.0}" \
    --port "${SERVER__PORT:-8000}" \
    --workers "${SERVER__WORKERS:-1}" \
    --log-level "${LOG_LEVEL:-info}"
