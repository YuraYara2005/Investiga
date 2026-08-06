# Investiga – Docker Deployment Guide

## Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Environment Variables](#environment-variables)
5. [Service Reference](#service-reference)
6. [Rebuilding the Backend](#rebuilding-the-backend)
7. [Resetting Volumes](#resetting-volumes)
8. [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     investiga_network (bridge)              │
│                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │   postgres   │   │    qdrant    │   │    backend     │  │
│  │  port 5432   │   │  port 6333   │   │   port 8000    │  │
│  │  postgres:16 │   │qdrant:latest │   │ python:3.12    │  │
│  └──────┬───────┘   └──────┬───────┘   └───────┬────────┘  │
│         │                  │                    │           │
│    postgres_data       qdrant_storage    depends on both    │
│    (named volume)      (named volume)   (healthy checks)   │
└─────────────────────────────────────────────────────────────┘
           │                  │                    │
        :5432              :6333/:6334           :8000
      (host port)         (host ports)         (host port)
```

**Startup sequence enforced by Docker Compose:**

1. `postgres` starts and passes its `pg_isready` healthcheck.
2. `qdrant` starts and passes its `/readyz` healthcheck.
3. `backend` container starts:
   - `wait_for_db.py` polls PostgreSQL TCP until connected.
   - `entrypoint.sh` polls Qdrant `/readyz` until 200 OK.
   - `alembic upgrade head` runs migrations.
   - `uvicorn app.main:app` begins serving on `:8000`.

---

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Docker Engine | 24.x |
| Docker Compose plugin | v2.20+ |

Verify:
```bash
docker --version
docker compose version
```

---

## Quick Start

```bash
# 1. Clone the repository (if not already done)
git clone <repo-url> && cd Investiga

# 2. Create your environment file from the template
cp .env.docker.example .env.docker

# 3. Edit secrets and API keys
#    Minimum: set SECURITY__SECRET_KEY and RAG__GEMINI_API_KEY
nano .env.docker          # or use your preferred editor

# 4. Build and start all services
docker compose up --build

# 5. Verify the backend is healthy
curl http://localhost:8000/health
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

The API interactive docs are available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Environment Variables

All application variables use the **double-underscore `__` nested delimiter** defined in the Pydantic Settings system (e.g. `DATABASE__URL` maps to `Settings.database.url`).

> [!IMPORTANT]
> `DATABASE__URL` and `VECTORSTORE__HOST` are **set directly in `docker-compose.yml`** using compose service names (`postgres`, `qdrant`). Do **not** override them in `.env.docker` — your values will be ignored.

### PostgreSQL credentials

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `postgres` | DB superuser username |
| `POSTGRES_PASSWORD` | `postgres` | DB superuser password |
| `POSTGRES_DB` | `investiga_db` | Database name to create |
| `POSTGRES_PORT` | `5432` | Host-side port binding |

### Backend application

| Variable | Default | Description |
|---|---|---|
| `APP__ENVIRONMENT` | `production` | Runtime env (`development`/`staging`/`production`) |
| `APP__DEBUG` | `false` | Enable debug mode |
| `SECURITY__SECRET_KEY` | *(required)* | JWT signing secret — use `openssl rand -hex 32` |
| `SECURITY__ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `LOGGING__LOG_LEVEL` | `INFO` | Log level (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `LOGGING__JSON_LOGS` | `true` | JSON-formatted logs (recommended in containers) |
| `RAG__LLM_PROVIDER` | `gemini` | LLM provider (`gemini`/`ollama`/`mock`) |
| `RAG__GEMINI_API_KEY` | *(required for Gemini)* | Google Gemini API key |

### Port bindings (host-side only)

| Variable | Default | Service |
|---|---|---|
| `BACKEND_PORT` | `8000` | FastAPI backend |
| `QDRANT_HTTP_PORT` | `6333` | Qdrant REST API |
| `QDRANT_GRPC_PORT` | `6334` | Qdrant gRPC |
| `POSTGRES_PORT` | `5432` | PostgreSQL |

---

## Service Reference

### PostgreSQL (`investiga_postgres`)

- Image: `postgres:16`
- Data volume: `postgres_data` → `/var/lib/postgresql/data`
- Healthcheck: `pg_isready -U <user> -d <db>`

Access from host:
```bash
psql -h localhost -U postgres -d investiga_db
```

Access from another container on `investiga_network`:
```
host=postgres  port=5432
```

### Qdrant (`investiga_qdrant`)

- Image: `qdrant/qdrant:latest`
- Data volume: `qdrant_storage` → `/qdrant/storage`
- REST API: `:6333` — Dashboard: http://localhost:6333/dashboard
- gRPC: `:6334`
- Healthcheck: `GET /readyz`

### Backend (`investiga_backend`)

- Built from `docker/backend/Dockerfile` (context: repo root)
- Runs as non-root user `appuser`
- Entrypoint: `docker/backend/entrypoint.sh`

---

## Rebuilding the Backend

After code changes to `backend/`:

```bash
# Rebuild only the backend image and restart
docker compose up --build backend

# Or force a clean rebuild (no layer cache)
docker compose build --no-cache backend
docker compose up backend
```

After dependency changes in `backend/requirements.txt`:

```bash
docker compose build --no-cache backend
docker compose up --build
```

---

## Resetting Volumes

> [!WARNING]
> The following commands **permanently delete** all PostgreSQL data and Qdrant vectors. This cannot be undone.

```bash
# Stop all services
docker compose down

# Remove named volumes (drops all data)
docker compose down -v

# Alternatively, remove specific volumes
docker volume rm investiga_postgres_data
docker volume rm investiga_qdrant_storage
```

To start completely fresh:
```bash
docker compose down -v && docker compose up --build
```

---

## Troubleshooting

### Backend exits immediately after starting

**Symptom:** Container exits with code 1 before uvicorn starts.

**Cause:** PostgreSQL or Qdrant failed their healthchecks before the `depends_on` condition was met, or Alembic migration failed.

**Resolution:**
```bash
# Check postgres health
docker compose ps
docker compose logs postgres

# Check migration output
docker compose logs backend | grep -i alembic

# Run migrations manually
docker compose run --rm backend alembic upgrade head
```

---

### `ModuleNotFoundError` in backend container

**Symptom:** `No module named 'app'` or similar.

**Cause:** The `WORKDIR` is `/app` and Alembic's `prepend_sys_path = .` in `alembic.ini` both expect the working directory to contain the `app/` package. The Dockerfile copies `backend/` into `/app`, so `app/` is at `/app/app/`.

**Resolution:** This is handled correctly by the Dockerfile. If you see this error, verify that `WORKDIR /app` is set and that `COPY backend/ ./` runs before any `alembic` commands.

---

### `database connection refused` during startup

**Symptom:** `wait_for_db.py` keeps printing `not ready yet`.

**Cause:** PostgreSQL container is still initializing.

**Resolution:** The `wait_for_db.py` script retries for 60 seconds by default. You can increase the timeout:
```bash
# In .env.docker
DB_WAIT_TIMEOUT=120
```

---

### Qdrant healthcheck fails

**Symptom:** `backend` never starts because `qdrant` is not healthy.

**Resolution:**
```bash
docker compose logs qdrant

# Test manually
curl http://localhost:6333/readyz
```

If Qdrant responds but the healthcheck still fails, verify `curl` is available in the qdrant image:
```bash
docker compose exec qdrant curl http://localhost:6333/readyz
```

---

### Port already in use

**Symptom:** `bind: address already in use` on host port 8000, 5432, or 6333.

**Resolution:** Change the host-side binding in `.env.docker`:
```env
BACKEND_PORT=8001
POSTGRES_PORT=5433
QDRANT_HTTP_PORT=6334
```

---

### View live logs

```bash
# All services
docker compose logs -f

# Single service
docker compose logs -f backend
docker compose logs -f postgres
docker compose logs -f qdrant
```
