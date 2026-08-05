"""Database package initialization for Investiga.

Exports declarative Base, mixins, naming conventions, asynchronous engine factories,
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
    "CONSTRAINT_NAMING_CONVENTIONS",
    "Base",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "check_database_connection",
    "create_database_engine",
    "create_session_factory",
    "dispose_database_engine",
    "get_database_engine",
    "get_db_session",
    "get_session_factory",
    "get_standalone_session",
]
