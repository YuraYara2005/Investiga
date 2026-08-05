"""Root API Router for Investiga.

This module mounts versioned API subtrees (e.g. `/api/v1`) and exposes root-level
health redirects for legacy container load balancers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import get_settings

settings = get_settings()

root_api_router = APIRouter()

# Mount Version 1 API tree (/api/v1)
root_api_router.include_router(
    api_v1_router,
    prefix=settings.app.api_v1_prefix,
)

# Also expose /health at root level for external cloud load balancers
root_api_router.include_router(health_router, prefix="")
