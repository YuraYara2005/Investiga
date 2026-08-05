"""Knowledge Chunk Repository for Investiga.

This module provides data access routines for KnowledgeChunk relational entities,
encapsulating batch creation, document chunk sequence querying, deletion, and counting.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repositories.base import BaseRepository
from app.knowledge.models.knowledge_chunk import KnowledgeChunk


class KnowledgeChunkRepository(BaseRepository[KnowledgeChunk]):
    """Data access repository for KnowledgeChunk entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_cls=KnowledgeChunk)

    async def bulk_create(self, chunks: Sequence[KnowledgeChunk]) -> int:
        """Persist a collection of knowledge chunks in a single operation.

        Args:
            chunks: Sequence of KnowledgeChunk model instances.

        Returns:
            int: Number of persisted chunks.
        """
        if not chunks:
            return 0

        self._session.add_all(chunks)
        await self._session.flush()
        return len(chunks)

    async def get_by_document_id(
        self,
        document_id: uuid.UUID,
    ) -> Sequence[KnowledgeChunk]:
        """Retrieve all chunks belonging to a document ordered by their sequential index.

        Args:
            document_id: UUID of the parent document.

        Returns:
            Sequence[KnowledgeChunk]: Ordered list of chunk entities.
        """
        stmt = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
            .order_by(KnowledgeChunk.chunk_index.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def delete_by_document_id(self, document_id: uuid.UUID) -> int:
        """Delete all chunks associated with a specific document ID.

        Args:
            document_id: UUID of the parent document.

        Returns:
            int: Number of deleted chunk records.
        """
        stmt = sa_delete(KnowledgeChunk).where(
            KnowledgeChunk.document_id == document_id
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        cursor_result = cast(CursorResult[Any], result)
        return int(cursor_result.rowcount or 0)

    async def count_by_document_id(self, document_id: uuid.UUID) -> int:
        """Count total chunks stored for a specific document.

        Args:
            document_id: UUID of the parent document.

        Returns:
            int: Total count of chunk records.
        """
        stmt = (
            select(func.count())
            .select_from(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
