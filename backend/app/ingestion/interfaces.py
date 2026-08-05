"""Abstract Interfaces for the Document Ingestion Pipeline.

Defines the contract for orchestrating end-to-end document processing workflows.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.models import IngestionOptions, IngestionReport


class DocumentIngestionPipelineInterface(ABC):
    """Abstract interface defining the document ingestion workflow."""

    @abstractmethod
    async def ingest_document(
        self,
        document_id: uuid.UUID,
        session: AsyncSession,
        options: IngestionOptions | None = None,
    ) -> IngestionReport:
        """Execute the end-to-end ingestion pipeline for an existing registered document.

        Args:
            document_id: UUID of the target KnowledgeDocument.
            session: Active asynchronous SQLAlchemy database session.
            options: Optional execution parameters and strategy overrides.

        Returns:
            IngestionReport: Complete summary report with telemetry metrics.

        Raises:
            DocumentNotFoundException: If the document does not exist.
            DocumentAlreadyProcessingException: If document is already undergoing processing.
            IngestionPipelineException: If any pipeline stage fails.
        """
        pass

    @abstractmethod
    async def ingest_content(
        self,
        content: bytes | Path,
        filename: str,
        user_id: uuid.UUID,
        session: AsyncSession,
        mime_type: str | None = None,
        title: str | None = None,
        category: str | None = None,
        options: IngestionOptions | None = None,
    ) -> IngestionReport:
        """Upload, register, and immediately ingest a raw document payload.

        Args:
            content: Raw file bytes or filesystem Path.
            filename: Original document filename.
            user_id: Principal UUID of the uploading user.
            session: Active asynchronous SQLAlchemy database session.
            mime_type: Optional explicit MIME content type.
            title: Optional human-readable title.
            category: Optional document category classification.
            options: Optional execution parameters.

        Returns:
            IngestionReport: Complete summary report with telemetry metrics.
        """
        pass
