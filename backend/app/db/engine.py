"""Asynchronous Database Engine Management for Investiga.

This module provides an enterprise-grade async engine factory powered by SQLAlchemy 2.0
and asyncpg. It implements connection pooling, pre-ping health checks, automatic socket
recycling, and lifecycle management for clean startup validation and graceful shutdowns.
"""

from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def create_database_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create and configure a production-ready asynchronous SQLAlchemy database engine.

    Configuration parameters:
        - pool_pre_ping=True: Issues a lightweight ping ('SELECT 1') before checking out
          a connection from the pool, eliminating 'server closed the connection unexpectedly'
          errors caused by firewall timeouts or database restarts.
        - pool_size: Base number of active, persistent connections kept open in the pool.
        - max_overflow: Burst connection limit allowed during sudden traffic spikes.
        - pool_timeout: Maximum seconds to wait for an available connection before timing out.
        - pool_recycle: Proactively recycles connections older than N seconds to avoid
          stale TCP connections dropped by intermediate proxies or AWS NLBs.
        - echo: Configures raw SQL statement logging for debugging (false in production).

    Args:
        settings: Application settings. If None, loaded via `get_settings()`.

    Returns:
        AsyncEngine: Configured asynchronous SQLAlchemy engine.
    """
    if settings is None:
        settings = get_settings()

    db_url = str(settings.database.url)

    logger.info(
        "initializing_database_engine",
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_recycle=settings.database.pool_recycle,
        echo=settings.database.echo_sql,
    )

    engine: AsyncEngine = create_async_engine(
        url=db_url,
        echo=settings.database.echo_sql,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_recycle=settings.database.pool_recycle,
        pool_pre_ping=True,
        future=True,
    )

    return engine


@lru_cache(maxsize=1)
def get_database_engine() -> AsyncEngine:
    """Retrieve the cached singleton asynchronous database engine instance."""
    return create_database_engine()


async def check_database_connection(engine: AsyncEngine) -> bool:
    """Execute a lightweight connectivity probe against PostgreSQL.

    Args:
        engine: The AsyncEngine instance to test.

    Returns:
        bool: True if database is reachable and accepting queries, False otherwise.
    """
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        logger.info("database_connectivity_check_passed")
        return True
    except Exception as exc:
        logger.error(
            "database_connectivity_check_failed",
            error=str(exc),
            exc_info=True,
        )
        return False


async def dispose_database_engine(engine: AsyncEngine | None = None) -> None:
    """Gracefully close all pooled database connections during application teardown.

    Args:
        engine: The AsyncEngine to dispose. If None, disposes the cached singleton.
    """
    target_engine = engine or get_database_engine()
    logger.info("disposing_database_engine_connection_pool")
    await target_engine.dispose()
    logger.info("database_engine_connection_pool_disposed")
