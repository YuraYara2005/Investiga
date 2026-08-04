"""Application Lifespan Management for Investiga.

This module coordinates asynchronous application startup and shutdown events using
FastAPI's modern lifespan context manager. It guarantees deterministic initialization
and clean resource teardown for the logging subsystem, database connection pools,
and future infrastructure providers (Redis, Qdrant, AI model caches).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import sys

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.logging import get_logger, setup_logging
from app.db.engine import (
    check_database_connection,
    dispose_database_engine,
    get_database_engine,
)

logger = get_logger(__name__)


async def _startup_infrastructure(settings: Settings) -> None:
    """Initialize and validate core platform infrastructure during server boot.

    Executes in sequential dependency order:
        1. Configures the unified Structlog pipeline.
        2. Validates cross-domain environment integrity.
        3. Initializes the SQLAlchemy 2.0 Async connection pool.
        4. Verifies live PostgreSQL connectivity with a fail-fast health probe.

    Raises:
        RuntimeError: If critical infrastructure (e.g. database) is unreachable.
    """
    # 1. Initialize logging subsystem
    setup_logging(settings=settings)

    logger.info(
        "application_startup_initiated",
        app_name=settings.app.name,
        environment=settings.app.environment,
        version=settings.app.version,
        python_version=sys.version.split()[0],
        debug_mode=settings.app.debug,
    )

    # 2. Validate configuration integrity
    settings.validate_environment_integrity()

    # 3. Verify Database Engine Connectivity (Fail-Fast)
    engine = get_database_engine()
    db_connected = await check_database_connection(engine=engine)

    if not db_connected:
        if not settings.app.is_testing:
            error_msg = (
                "FATAL: Database connectivity check failed during application startup. "
                "Verify that PostgreSQL is running and DATABASE__URL is valid."
            )
            logger.critical("startup_database_connection_failed", message=error_msg)
            raise RuntimeError(error_msg)
        else:
            logger.warning("testing_mode_bypassing_database_startup_failure")

    # Future Extension Points:
    # 4. Initialize Redis Connection Pool (Phase 2)
    # 5. Initialize Qdrant Vector Search Client (Phase 2)
    # 6. Preload Local Embedding Models / Tokenizers (Phase 2)

    logger.info(
        "application_startup_completed",
        status="ready",
        api_v1_prefix=settings.app.api_v1_prefix,
    )


async def _shutdown_infrastructure(settings: Settings) -> None:
    """Gracefully dispose and release shared infrastructure during server shutdown.

    Executes in reverse dependency order with defensive error handling to ensure
    all teardown steps attempt execution even if one raises an exception.
    """
    logger.info("application_shutdown_initiated")

    # 1. Dispose Database Connection Pool
    try:
        await dispose_database_engine()
        logger.info("database_resources_released")
    except Exception as exc:
        logger.error(
            "database_shutdown_cleanup_error",
            error=str(exc),
            exc_info=True,
        )

    # Future Extension Points:
    # 2. Close Redis Connection Pool (Phase 2)
    # 3. Close Qdrant Client Sessions (Phase 2)
    # 4. Drain Background Task Queues & Workers (Phase 2)

    logger.info("application_shutdown_completed", status="terminated")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI application lifespan context manager.

    Coordinates asynchronous startup initialization and graceful shutdown teardown
    around the FastAPI request-handling lifecycle.

    Args:
        app: The FastAPI application instance being managed.

    Yields:
        None: Control is yielded to FastAPI to begin processing HTTP requests.
    """
    settings = get_settings()

    # --- Startup Phase ---
    await _startup_infrastructure(settings=settings)

    try:
        # Control is yielded to FastAPI to serve HTTP requests
        yield
    finally:
        # --- Shutdown Phase ---
        await _shutdown_infrastructure(settings=settings)
