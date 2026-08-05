"""Abstract Base Parser for Document Extraction.

Defines the contractual interface and common lifecycle methods that every format-specific
document parser (PDF, DOCX, Markdown, Plaintext) must implement.
"""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

from app.document_processing.models import ExtractedDocument, ExtractedMetadata


class BaseDocumentParser(ABC):
    """Contractual abstract base class for all file format parsers."""

    @abstractmethod
    def supports(self, extension: str, mime_type: str | None = None) -> bool:
        """Evaluate if this parser supports the given file extension and/or MIME type.

        Args:
            extension: Lowercase file extension with leading dot (e.g. '.pdf').
            mime_type: Optional MIME content type (e.g. 'application/pdf').

        Returns:
            bool: True if parser can process the document format.
        """
        ...

    @abstractmethod
    def extract_text(self, content: bytes | Path) -> str:
        """Extract raw text from file binary content or filesystem path.

        Args:
            content: Raw byte payload or Path to the file.

        Returns:
            str: Raw extracted text.
        """
        ...

    @abstractmethod
    def extract_metadata(self, content: bytes | Path) -> ExtractedMetadata:
        """Extract document properties, timestamps, and page count from the file.

        Args:
            content: Raw byte payload or Path to the file.

        Returns:
            ExtractedMetadata: Normalized metadata container.
        """
        ...

    def parse(self, content: bytes | Path) -> ExtractedDocument:
        """Synchronously execute text extraction and metadata retrieval.

        Args:
            content: Raw byte payload or Path to the file.

        Returns:
            ExtractedDocument: Combined extraction output.
        """
        raw_text = self.extract_text(content)
        metadata = self.extract_metadata(content)
        return ExtractedDocument(raw_text=raw_text, metadata=metadata)

    async def parse_async(self, content: bytes | Path) -> ExtractedDocument:
        """Asynchronously parse document offloading CPU/I/O execution to worker thread pool.

        Args:
            content: Raw byte payload or Path to the file.

        Returns:
            ExtractedDocument: Combined extraction output.
        """
        return await asyncio.to_thread(self.parse, content)
