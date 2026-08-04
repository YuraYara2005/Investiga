"""Asynchronous Session Management and Dependency Injection for Investiga.

This module provides an asynchronous session factory powered by `async_sessionmaker`
and implements the FastAPI dependency `get_db_session` for automated transaction
lifecycle management (automatic commit, exception rollback, and guaranteed connection cleanup).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.db.engine import get_database_engine

logger = get_logger(__name__)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create an asynchronous session factory bound to the supplied engine.

    Design Configuration:
        - `expire_on_commit=False`: Crucial for async SQLAlchemy. Prevents SQLAlchemy
          from expiring mapped object attributes after commit, which would otherwise
          trigger synchronous lazy-load I/O operations and throw MissingGreenlet exceptions.
        - `autoflush=False`: Ensures queries do not trigger unexpected premature flushes
          before explicit transaction boundaries.
        - `class_=AsyncSession`: Strictly binds sessions to the asynchronous session driver.

    Args:
        engine: The AsyncEngine instance to bind.

    Returns:
        async_sessionmaker[AsyncSession]: Configured async session factory.
    """
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Retrieve the cached singleton session factory."""
    engine = get_database_engine()
    return create_session_factory(engine=engine)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an isolated asynchronous database session.

    Implements the Unit of Work transaction lifecycle:
        1. Opens an isolated AsyncSession from the connection pool.
        2. Yields the session to the requesting route handler / service.
        3. Automatically commits the transaction if no unhandled exceptions occurred.
        4. Rolls back the transaction immediately if an exception is raised.
        5. Closes the session and returns the connection to the pool in all cases.

    Yields:
        AsyncSession: Active asynchronous database session.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error(
                "database_transaction_rolled_back",
                error=str(exc),
                exc_info=True,
            )
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_standalone_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for standalone async tasks, background workers, and scripts.

    Yields:
        AsyncSession: Active asynchronous database session.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error(
                "standalone_database_transaction_rolled_back",
                error=str(exc),
                exc_info=True,
            )
            raise
        finally:
            await session.close()
