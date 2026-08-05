"""Knowledge Document Repository for Investiga.

This module provides data access routines for KnowledgeDocument entities,
encapsulating pagination, multi-attribute filtering, metadata search,
and cryptographic checksum uniqueness verification.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, or_, select
from sqlalchemy import update as sa_update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repositories.base import BaseRepository
from app.knowledge.models import (
    DocumentCategory,
    EmbeddingStatus,
    KnowledgeDocument,
    ProcessingStatus,
)


class KnowledgeRepository(BaseRepository[KnowledgeDocument]):
    """Data access repository for KnowledgeDocument entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_cls=KnowledgeDocument)

    async def get_by_checksum(
        self, checksum: str, include_deleted: bool = False
    ) -> KnowledgeDocument | None:
        """Retrieve a document by its cryptographic SHA-256 checksum.

        Args:
            checksum: SHA-256 hex digest string.
            include_deleted: Whether to include soft-deleted documents.

        Returns:
            KnowledgeDocument | None: Matching document or None.
        """
        stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.checksum == checksum.strip().lower()
        )
        if not include_deleted:
            stmt = stmt.where(KnowledgeDocument.is_deleted.is_(False))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_checksum(
        self, checksum: str, include_deleted: bool = False
    ) -> bool:
        """Check whether a document with the given checksum already exists.

        Args:
            checksum: SHA-256 hex digest string.
            include_deleted: Whether to check against soft-deleted documents.

        Returns:
            bool: True if a matching document exists, False otherwise.
        """
        stmt = (
            select(func.count())
            .select_from(KnowledgeDocument)
            .where(KnowledgeDocument.checksum == checksum.strip().lower())
        )
        if not include_deleted:
            stmt = stmt.where(KnowledgeDocument.is_deleted.is_(False))

        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def list_documents(
        self,
        skip: int = 0,
        limit: int = 50,
        category: DocumentCategory | None = None,
        processing_status: ProcessingStatus | None = None,
        embedding_status: EmbeddingStatus | None = None,
        uploaded_by: uuid.UUID | None = None,
        sort_by: str = "created_at",
        sort_desc: bool = True,
        include_deleted: bool = False,
    ) -> Sequence[KnowledgeDocument]:
        """Query a paginated, filtered, and sorted sequence of knowledge documents.

        Args:
            skip: Offset number of records.
            limit: Maximum records to return.
            category: Optional category discriminator filter.
            processing_status: Optional processing pipeline status filter.
            embedding_status: Optional vector embedding status filter.
            uploaded_by: Optional uploader UUID filter.
            sort_by: Target model column name to sort by ('created_at', 'title', 'file_size').
            sort_desc: Whether sort order is descending (default True).
            include_deleted: Whether to include soft-deleted records.

        Returns:
            Sequence[KnowledgeDocument]: Filtered and ordered list of documents.
        """
        stmt = select(KnowledgeDocument)

        if not include_deleted:
            stmt = stmt.where(KnowledgeDocument.is_deleted.is_(False))

        if category is not None:
            stmt = stmt.where(KnowledgeDocument.category == category)

        if processing_status is not None:
            stmt = stmt.where(KnowledgeDocument.processing_status == processing_status)

        if embedding_status is not None:
            stmt = stmt.where(KnowledgeDocument.embedding_status == embedding_status)

        if uploaded_by is not None:
            stmt = stmt.where(KnowledgeDocument.uploaded_by == uploaded_by)

        # Dynamic column sorting
        sort_column = getattr(KnowledgeDocument, sort_by, KnowledgeDocument.created_at)
        if sort_desc:
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())

        stmt = stmt.offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def search_metadata(
        self,
        query: str,
        skip: int = 0,
        limit: int = 50,
        category: DocumentCategory | None = None,
        include_deleted: bool = False,
    ) -> Sequence[KnowledgeDocument]:
        """Search documents across title, description, and original filename metadata.

        Args:
            query: Substring search term.
            skip: Pagination offset.
            limit: Pagination page size.
            category: Optional category filter.
            include_deleted: Whether to include soft-deleted documents.

        Returns:
            Sequence[KnowledgeDocument]: Matching documents.
        """
        pattern = f"%{query.strip()}%"
        stmt = select(KnowledgeDocument).where(
            or_(
                KnowledgeDocument.title.ilike(pattern),
                KnowledgeDocument.description.ilike(pattern),
                KnowledgeDocument.original_filename.ilike(pattern),
            )
        )

        if not include_deleted:
            stmt = stmt.where(KnowledgeDocument.is_deleted.is_(False))

        if category is not None:
            stmt = stmt.where(KnowledgeDocument.category == category)

        stmt = stmt.order_by(KnowledgeDocument.created_at.desc())
        stmt = stmt.offset(skip).limit(limit)

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_documents(
        self,
        category: DocumentCategory | None = None,
        processing_status: ProcessingStatus | None = None,
        embedding_status: EmbeddingStatus | None = None,
        uploaded_by: uuid.UUID | None = None,
        search_query: str | None = None,
        include_deleted: bool = False,
    ) -> int:
        """Count total documents satisfying the specified criteria.

        Args:
            category: Optional category filter.
            processing_status: Optional pipeline status filter.
            embedding_status: Optional vector embedding status filter.
            uploaded_by: Optional uploader filter.
            search_query: Optional search term.
            include_deleted: Whether to count soft-deleted records.

        Returns:
            int: Total count of matching documents.
        """
        stmt = select(func.count()).select_from(KnowledgeDocument)

        if not include_deleted:
            stmt = stmt.where(KnowledgeDocument.is_deleted.is_(False))

        if category is not None:
            stmt = stmt.where(KnowledgeDocument.category == category)

        if processing_status is not None:
            stmt = stmt.where(KnowledgeDocument.processing_status == processing_status)

        if embedding_status is not None:
            stmt = stmt.where(KnowledgeDocument.embedding_status == embedding_status)

        if uploaded_by is not None:
            stmt = stmt.where(KnowledgeDocument.uploaded_by == uploaded_by)

        if search_query:
            pattern = f"%{search_query.strip()}%"
            stmt = stmt.where(
                or_(
                    KnowledgeDocument.title.ilike(pattern),
                    KnowledgeDocument.description.ilike(pattern),
                    KnowledgeDocument.original_filename.ilike(pattern),
                )
            )

        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def soft_delete(self, document_id: uuid.UUID) -> bool:
        """Logically mark a document as deleted and record deletion timestamp.

        Args:
            document_id: UUID of the document to soft-delete.

        Returns:
            bool: True if document was marked deleted, False if not found or already deleted.
        """
        stmt = (
            sa_update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .where(KnowledgeDocument.is_deleted.is_(False))
            .values(
                is_deleted=True,
                deleted_at=datetime.now(UTC),
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        cursor_result = cast(CursorResult[Any], result)
        return bool(cursor_result.rowcount and cursor_result.rowcount > 0)
