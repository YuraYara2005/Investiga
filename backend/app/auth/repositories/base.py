"""Generic Asynchronous Base Repository for Investiga.

This module implements the foundational Generic Repository pattern using SQLAlchemy 2.0
and AsyncSession. It provides robust, DRY CRUD operations, soft-delete filtering,
and pagination while remaining completely transaction-agnostic.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar, cast

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic asynchronous repository encapsulating standard database operations.

    Repositories are strictly transaction-agnostic: they perform `flush()` to synchronize
    state and acquire auto-generated IDs, but never call `commit()` or `rollback()`.
    Transaction boundaries are managed by the calling service or unit of work.

    Attributes:
        session: Active asynchronous database session.
        model_cls: SQLAlchemy model class managed by this repository instance.
    """

    def __init__(self, session: AsyncSession, model_cls: type[ModelType]) -> None:
        self._session = session
        self._model_cls = model_cls

    @property
    def session(self) -> AsyncSession:
        """Provide access to the underlying AsyncSession for specialized query extensions."""
        return self._session

    @property
    def model_cls(self) -> type[ModelType]:
        """Provide access to the managed model class."""
        return self._model_cls

    @property
    def _model(self) -> Any:
        """Dynamic reference to model class for building SQLAlchemy column expressions."""
        return self._model_cls

    async def create(self, entity: ModelType) -> ModelType:
        """Persist a new entity to the database session and flush state.

        Args:
            entity: The model instance to persist.

        Returns:
            ModelType: The persisted entity with populated primary key and defaults.
        """
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def get_by_id(
        self, entity_id: uuid.UUID, include_deleted: bool = False
    ) -> ModelType | None:
        """Retrieve a single entity by its primary key UUID.

        Args:
            entity_id: The entity's primary key UUID.
            include_deleted: Whether to return soft-deleted records.

        Returns:
            ModelType | None: The found entity or None.
        """
        stmt = select(self._model_cls).where(self._model.id == entity_id)

        if not include_deleted and hasattr(self._model_cls, "is_deleted"):
            stmt = stmt.where(self._model.is_deleted.is_(False))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> Sequence[ModelType]:
        """Retrieve a paginated collection of entities.

        Args:
            skip: Number of records to skip (offset).
            limit: Maximum number of records to return.
            include_deleted: Whether to include soft-deleted records.

        Returns:
            Sequence[ModelType]: Ordered sequence of entities.
        """
        stmt = select(self._model_cls).offset(skip).limit(limit)

        if not include_deleted and hasattr(self._model_cls, "is_deleted"):
            stmt = stmt.where(self._model.is_deleted.is_(False))

        if hasattr(self._model_cls, "created_at"):
            stmt = stmt.order_by(self._model.created_at.desc())

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update(self, entity: ModelType) -> ModelType:
        """Flush changes for an existing entity and refresh its state.

        Args:
            entity: The modified model instance attached to the session.

        Returns:
            ModelType: The refreshed entity.
        """
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def delete(self, entity_id: uuid.UUID, hard_delete: bool = False) -> bool:
        """Delete an entity by ID, executing soft-delete by default if supported.

        Args:
            entity_id: UUID of the entity to delete.
            hard_delete: If True, issues a permanent SQL DELETE statement.

        Returns:
            bool: True if an entity was deleted, False if entity was not found.
        """
        if not hard_delete and hasattr(self._model_cls, "is_deleted"):
            # Perform soft-delete update
            update_stmt = (
                sa_update(self._model_cls)
                .where(self._model.id == entity_id)
                .where(self._model.is_deleted.is_(False))
                .values(
                    is_deleted=True,
                    deleted_at=datetime.now(UTC),
                )
            )
            result = await self._session.execute(update_stmt)
            await self._session.flush()
            cursor_result = cast(CursorResult[Any], result)
            return bool(cursor_result.rowcount and cursor_result.rowcount > 0)
        else:
            # Perform permanent hard delete
            delete_stmt = sa_delete(self._model_cls).where(
                self._model.id == entity_id
            )
            result = await self._session.execute(delete_stmt)
            await self._session.flush()
            cursor_result = cast(CursorResult[Any], result)
            return bool(cursor_result.rowcount and cursor_result.rowcount > 0)

    async def exists(self, entity_id: uuid.UUID) -> bool:
        """Check whether an active entity exists with the specified UUID.

        Args:
            entity_id: UUID to check.

        Returns:
            bool: True if entity exists and is not soft-deleted, False otherwise.
        """
        stmt = (
            select(func.count())
            .select_from(self._model_cls)
            .where(self._model.id == entity_id)
        )
        if hasattr(self._model_cls, "is_deleted"):
            stmt = stmt.where(self._model.is_deleted.is_(False))

        result = await self._session.execute(stmt)
        count = result.scalar_one()
        return count > 0

    async def count(self, include_deleted: bool = False) -> int:
        """Count the total number of entities in the table.

        Args:
            include_deleted: Whether to count soft-deleted records.

        Returns:
            int: Total entity count.
        """
        stmt = select(func.count()).select_from(self._model_cls)

        if not include_deleted and hasattr(self._model_cls, "is_deleted"):
            stmt = stmt.where(self._model.is_deleted.is_(False))

        result = await self._session.execute(stmt)
        return result.scalar_one()
