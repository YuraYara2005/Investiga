"""Health and Diagnostic Probes for Investiga.

This module provides Kubernetes-compliant Liveness, Readiness, and Comprehensive
Health check endpoints for container orchestrators and observability platforms.
"""

import time
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_settings, get_database
from app.core.config import Settings
from app.core.logging import get_logger
from app.exceptions import ServiceUnavailableException

logger = get_logger(__name__)

router = APIRouter(tags=["Health & Monitoring"])


class ComponentHealth(BaseModel):
    """Health diagnostic status of an individual platform dependency."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Operational status of the specific component."
    )
    latency_ms: float | None = Field(
        default=None, description="Round-trip latency probe in milliseconds."
    )
    details: str | None = Field(
        default=None, description="Optional diagnostic notes or error context."
    )


class HealthResponse(BaseModel):
    """Comprehensive health check response envelope."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Overall platform operational status."
    )
    application: str = Field(..., description="Application name.")
    version: str = Field(..., description="Application version.")
    environment: str = Field(..., description="Runtime deployment environment.")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp.")
    components: dict[str, ComponentHealth] = Field(
        default_factory=dict,
        description="Detailed subsystem component statuses (Database, Redis, Qdrant).",
    )


class LivenessResponse(BaseModel):
    """Lightweight response for Kubernetes liveness probes."""

    status: Literal["alive"] = "alive"
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ReadinessResponse(BaseModel):
    """Response envelope for Kubernetes readiness probes."""

    status: Literal["ready"] = "ready"
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    components: dict[str, ComponentHealth] = Field(default_factory=dict)


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Comprehensive Platform Health Check",
    description="Returns full operational health status and latency telemetry across all connected subsystems.",
)
async def get_health(
    settings: Settings = Depends(get_current_settings),
    db: AsyncSession = Depends(get_database),
) -> HealthResponse:
    """Perform a comprehensive health check across application and dependent systems."""
    components: dict[str, ComponentHealth] = {}
    is_all_healthy = True

    # 1. Database Connectivity Probe
    start_time = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        components["database"] = ComponentHealth(
            status="healthy",
            latency_ms=latency,
        )
    except Exception as exc:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(
            "health_check_database_probe_failed",
            error=str(exc),
            latency_ms=latency,
        )
        components["database"] = ComponentHealth(
            status="unhealthy",
            latency_ms=latency,
            details="Database ping failed.",
        )
        is_all_healthy = False

    # Future Extensions (Phase 2):
    # components["redis"] = await check_redis_health()
    # components["qdrant"] = await check_qdrant_health()

    overall_status: Literal["healthy", "degraded", "unhealthy"] = (
        "healthy" if is_all_healthy else "degraded"
    )

    return HealthResponse(
        status=overall_status,
        application=settings.app.name,
        version=settings.app.version,
        environment=settings.app.environment,
        timestamp=datetime.now(UTC).isoformat(),
        components=components,
    )


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Kubernetes Liveness Probe",
    description="Indicates whether the application process is running and responding. Never checks external dependencies.",
)
async def get_liveness() -> LivenessResponse:
    """Kubernetes liveness probe. Fails only if the ASGI event loop is deadlocked."""
    return LivenessResponse(
        status="alive",
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Kubernetes Readiness Probe",
    description="Indicates whether the application is ready to accept user traffic. Verifies critical database connectivity.",
)
async def get_readiness(
    db: AsyncSession = Depends(get_database),
) -> ReadinessResponse:
    """Kubernetes readiness probe. Returns 503 if PostgreSQL is unreachable."""
    start_time = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        db_component = ComponentHealth(status="healthy", latency_ms=latency)
    except Exception as exc:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("readiness_check_failed", error=str(exc), latency_ms=latency)
        raise ServiceUnavailableException(
            message="Application is not ready: database connection unavailable.",
            details={"component": "database", "latency_ms": latency},
        ) from exc

    return ReadinessResponse(
        status="ready",
        timestamp=datetime.now(UTC).isoformat(),
        components={"database": db_component},
    )
