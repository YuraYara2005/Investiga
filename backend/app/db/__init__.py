"""Database package initialization for Investiga.

Exports declarative models, naming conventions, asynchronous engine factories,
and session dependency injection utilities.
"""

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.engine import (
    check_database_connection,
    create_database_engine,
    dispose_database_engine,
    get_database_engine,
)
from app.db.naming import CONSTRAINT_NAMING_CONVENTIONS
from app.db.session import (
    create_session_factory,
    get_db_session,
    get_session_factory,
    get_standalone_session,
)

__all__ = [
    "Base",
    "UUIDPrimaryKeyMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    "CONSTRAINT_NAMING_CONVENTIONS",
    "create_database_engine",
    "get_database_engine",
    "check_database_connection",
    "dispose_database_engine",
    "create_session_factory",
    "get_session_factory",
    "get_db_session",
    "get_standalone_session",
]
