"""API v1 Central Router for Investiga.

This module aggregates all Version 1 endpoint routers into a cohesive,
versioned routing subtree under the `/api/v1` namespace.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.health import router as health_router

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
# Future Business Domain Routes (Phase 2+ / Phase 3+)
# ------------------------------------------------------------------------------
# api_v1_router.include_router(users_router, prefix="/users", tags=["Users & RBAC"])
# api_v1_router.include_router(investigations_router, prefix="/investigations", tags=["Investigations"])
# api_v1_router.include_router(knowledge_router, prefix="/knowledge", tags=["Knowledge Base"])
# api_v1_router.include_router(search_router, prefix="/search", tags=["Hybrid Search & Retrieval"])
# api_v1_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics & Telemetry"])
# api_v1_router.include_router(evaluation_router, prefix="/evaluation", tags=["RAG & LLM Evaluation"])
