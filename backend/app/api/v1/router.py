"""API v1 Central Router for Investiga.

This module aggregates all Version 1 endpoint routers into a cohesive,
versioned routing subtree under the `/api/v1` namespace.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.knowledge import router as knowledge_router

api_v1_router = APIRouter()

# ------------------------------------------------------------------------------
# Core Platform Endpoints
# ------------------------------------------------------------------------------
api_v1_router.include_router(health_router, prefix="")

# ------------------------------------------------------------------------------
# Authentication & Identity Endpoints
# ------------------------------------------------------------------------------
api_v1_router.include_router(auth_router, prefix="")

# ------------------------------------------------------------------------------
# Knowledge Management Endpoints
# ------------------------------------------------------------------------------
api_v1_router.include_router(knowledge_router, prefix="")
