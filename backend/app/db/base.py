"""Declarative Base and Shared Mixins for Investiga Database Models.

This module establishes the root `Base` class configured with SQLAlchemy 2.0
declarative mapping, async attributes (`AsyncAttrs`), and deterministic constraint
naming conventions. It provides reusable mixins for UUID primary keys and audit timestamps.
"""

import re
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from app.db.naming import CONSTRAINT_NAMING_CONVENTIONS


class Base(AsyncAttrs, DeclarativeBase):
    """Root declarative base class for all relational database entities.

    Configured with `AsyncAttrs` to support asynchronous lazy loading when needed,
    and bound to a centralized `MetaData` instance enforcing standardized constraint
    naming conventions.
    """

    metadata = MetaData(naming_convention=CONSTRAINT_NAMING_CONVENTIONS)

    @declared_attr.directive
    def __tablename__(cls) -> str:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Derive standard snake_case table names automatically from PascalCase class names."""
        name = re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()
        return name


class UUIDPrimaryKeyMixin:
    """Mixin that equips models with a globally unique UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        doc="Universally unique identifier for the entity.",
    )


class TimestampMixin:
    """Mixin that equips models with timezone-aware audit timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp in UTC when the record was initially persisted.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Timestamp in UTC when the record was last modified.",
    )


class SoftDeleteMixin:
    """Mixin that equips models with soft-delete capabilities for enterprise audit trails."""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        doc="Flag indicating whether this entity has been logically marked as deleted.",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
        doc="Timestamp in UTC when the record was soft-deleted.",
    )
