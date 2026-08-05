"""Intelligent Document Processor Pipeline.

Orchestrates parser selection, asynchronous text extraction, Unicode normalization,
control character sanitization, structural whitespace preservation, and metadata synthesis.
"""

import time
import uuid
from pathlib import Path, PurePath

from app.core.logging import get_logger
from app.document_processing.cleaners import TextCleaner
from app.document_processing.exceptions import (
    CorruptedDocumentException,
    EmptyDocumentException,
    UnsupportedDocumentException,
)
from app.document_processing.models import ProcessingResult
from app.document_processing.parser_factory import DocumentParserFactory

logger = get_logger(__name__)


class DocumentProcessor:
    """Enterprise document processing and normalization pipeline."""

    def __init__(self, parser_factory: DocumentParserFactory | None = None) -> None:
        """Initialize processor with parser factory instance."""
        self._factory = parser_factory or DocumentParserFactory()

    async def process(
        self,
        content: bytes | Path,
        filename: str,
        mime_type: str | None = None,
        document_id: uuid.UUID | None = None,
        language: str | None = None,
    ) -> ProcessingResult:
        """Asynchronously process an uploaded document payload through extraction and cleaning pipelines.

        Args:
            content: Raw document binary bytes or filesystem Path.
            filename: Original or stored document filename.
            mime_type: Optional MIME content type.
            document_id: Optional document database identifier.
            language: Optional default language code override.

        Returns:
            ProcessingResult: Fully sanitized, normalized textual output with comprehensive metadata.

        Raises:
            UnsupportedDocumentException: If file format is not supported.
            CorruptedDocumentException: If file binary is damaged or unreadable.
            EmptyDocumentException: If file yields zero extractable text.
        """
        start_time = time.perf_counter()

        # 1. Resolve appropriate parser
        parser = self._factory.get_parser(
            filename_or_extension=filename,
            mime_type=mime_type,
        )

        # 2. Asynchronously extract text and metadata offloaded to threadpool
        try:
            extracted = await parser.parse_async(content)
        except (
            UnsupportedDocumentException,
            CorruptedDocumentException,
            EmptyDocumentException,
        ):
            raise
        except Exception as exc:
            logger.error(
                "document_extraction_failed",
                filename=filename,
                error=str(exc),
                document_id=str(document_id) if document_id else None,
                exc_info=True,
            )
            raise CorruptedDocumentException(
                filename=filename,
                reason=f"Extraction pipeline failure: {exc}",
            ) from exc

        raw_text = extracted.raw_text

        # 3. Clean and normalize extracted text
        clean_text = TextCleaner.clean(raw_text)

        # 4. Compute statistics
        word_count = TextCleaner.count_words(clean_text)
        character_count = TextCleaner.count_characters(clean_text)
        meta = extracted.metadata

        # 5. Resolve metadata title and language
        resolved_title = meta.title or PurePath(filename).stem
        resolved_language = language or meta.language or "en"

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        logger.info(
            "document_processed_successfully",
            filename=filename,
            document_id=str(document_id) if document_id else None,
            page_count=meta.page_count,
            word_count=word_count,
            character_count=character_count,
            processing_time_ms=round(elapsed_ms, 2),
        )

        return ProcessingResult(
            document_id=document_id,
            raw_text=raw_text,
            clean_text=clean_text,
            page_count=meta.page_count,
            word_count=word_count,
            character_count=character_count,
            language=resolved_language,
            title=resolved_title,
            author=meta.author,
            creation_date=meta.creation_date,
            modification_date=meta.modification_date,
            processing_time_ms=round(elapsed_ms, 2),
            metadata=meta.extra_metadata,
        )

    def process_sync(
        self,
        content: bytes | Path,
        filename: str,
        mime_type: str | None = None,
        document_id: uuid.UUID | None = None,
        language: str | None = None,
    ) -> ProcessingResult:
        """Synchronously process document payload (convenience method for scripts/tools)."""
        start_time = time.perf_counter()

        parser = self._factory.get_parser(
            filename_or_extension=filename,
            mime_type=mime_type,
        )

        try:
            extracted = parser.parse(content)
        except (
            UnsupportedDocumentException,
            CorruptedDocumentException,
            EmptyDocumentException,
        ):
            raise
        except Exception as exc:
            raise CorruptedDocumentException(
                filename=filename,
                reason=f"Extraction failure: {exc}",
            ) from exc

        raw_text = extracted.raw_text
        clean_text = TextCleaner.clean(raw_text)
        word_count = TextCleaner.count_words(clean_text)
        character_count = TextCleaner.count_characters(clean_text)
        meta = extracted.metadata

        resolved_title = meta.title or PurePath(filename).stem
        resolved_language = language or meta.language or "en"
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return ProcessingResult(
            document_id=document_id,
            raw_text=raw_text,
            clean_text=clean_text,
            page_count=meta.page_count,
            word_count=word_count,
            character_count=character_count,
            language=resolved_language,
            title=resolved_title,
            author=meta.author,
            creation_date=meta.creation_date,
            modification_date=meta.modification_date,
            processing_time_ms=round(elapsed_ms, 2),
            metadata=meta.extra_metadata,
        )
