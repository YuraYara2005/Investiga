"""Ingestion Application Service for Investiga.

Provides a unified high-level service layer coordinating asynchronous document ingestion,
session lifecycle, and re-indexing workflows for FastAPI endpoints and future background tasks.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.ingestion.models import IngestionOptions, IngestionReport
from app.ingestion.pipeline import DocumentIngestionPipeline

logger = get_logger(__name__)


class IngestionService:
    """Application service coordinating document ingestion operations."""

    def __init__(
        self,
        session: AsyncSession,
        pipeline: DocumentIngestionPipeline | None = None,
    ) -> None:
        """Initialize IngestionService with an active database session and optional pipeline.

        Args:
            session: Active asynchronous SQLAlchemy database session.
            pipeline: Document ingestion pipeline instance (constructed with defaults if None).
        """
        self._session = session
        self._pipeline = pipeline or DocumentIngestionPipeline()

    async def ingest_document(
        self,
        document_id: uuid.UUID,
        options: IngestionOptions | None = None,
    ) -> IngestionReport:
        """Trigger end-to-end ingestion for an existing registered document.

        Args:
            document_id: UUID of the document to ingest.
            options: Optional execution configuration overrides.

        Returns:
            IngestionReport: Detailed report with telemetry metrics.
        """
        return await self._pipeline.ingest_document(
            document_id=document_id,
            session=self._session,
            options=options,
        )

    async def reindex_document(
        self,
        document_id: uuid.UUID,
        options: IngestionOptions | None = None,
    ) -> IngestionReport:
        """Re-process and re-index an existing document, overwriting existing vectors.

        Args:
            document_id: UUID of the document to re-index.
            options: Optional execution configuration overrides.

        Returns:
            IngestionReport: Detailed report with telemetry metrics.
        """
        opts = options or IngestionOptions()
        # Enforce force_reindex
        reindex_options = IngestionOptions(
            chunk_size=opts.chunk_size,
            overlap=opts.overlap,
            chunk_strategy=opts.chunk_strategy,
            batch_size=opts.batch_size,
            force_reindex=True,
            metadata_override=opts.metadata_override,
        )
        return await self._pipeline.ingest_document(
            document_id=document_id,
            session=self._session,
            options=reindex_options,
        )

    async def ingest_content(
        self,
        content: bytes | Path,
        filename: str,
        user_id: uuid.UUID,
        mime_type: str | None = None,
        title: str | None = None,
        category: str | None = None,
        options: IngestionOptions | None = None,
    ) -> IngestionReport:
        """Upload, register, and immediately ingest a raw document payload.

        Args:
            content: Raw document binary or filesystem Path.
            filename: Original document filename.
            user_id: Principal UUID of the uploading user.
            mime_type: Optional MIME content type.
            title: Optional title.
            category: Optional category.
            options: Optional execution configuration overrides.

        Returns:
            IngestionReport: Detailed report with telemetry metrics.
        """
        return await self._pipeline.ingest_content(
            content=content,
            filename=filename,
            user_id=user_id,
            session=self._session,
            mime_type=mime_type,
            title=title,
            category=category,
            options=options,
        )
