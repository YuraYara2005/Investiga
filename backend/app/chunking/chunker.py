"""Chunking Engine Orchestrator.

Provides the high-level ChunkingEngine that integrates strategy selection,
async execution, and result aggregation into a single ProcessingResult-compatible interface.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from app.chunking.exceptions import InvalidChunkConfigException
from app.chunking.models import Chunk, ChunkResult
from app.chunking.strategies import (
    AdaptiveChunker,
    BaseChunkStrategy,
    FixedCharacterChunker,
    MarkdownHeaderChunker,
    ParagraphChunker,
    RecursiveCharacterChunker,
    SentenceChunker,
)
from app.chunking.tokenizer import Tokenizer, get_tokenizer
from app.core.logging import get_logger

logger = get_logger(__name__)

_STRATEGY_REGISTRY: dict[str, type[BaseChunkStrategy]] = {
    "fixed_character": FixedCharacterChunker,
    "recursive_character": RecursiveCharacterChunker,
    "sentence": SentenceChunker,
    "paragraph": ParagraphChunker,
    "markdown_header": MarkdownHeaderChunker,
    "adaptive": AdaptiveChunker,
}


class ChunkingEngine:
    """Enterprise document chunking engine integrating multiple strategies."""

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 64,
        strategy: str = "adaptive",
        tokenizer: Tokenizer | None = None,
    ) -> None:
        """Initialize the ChunkingEngine.

        Args:
            chunk_size: Maximum number of tokens per chunk.
            overlap: Number of overlapping tokens between consecutive chunks.
            strategy: Chunking strategy name or 'adaptive' for automatic selection.
            tokenizer: Optional pre-configured Tokenizer instance.

        Raises:
            InvalidChunkConfigException: If chunk_size or overlap are invalid.
        """
        if chunk_size <= 0:
            raise InvalidChunkConfigException(
                f"chunk_size must be > 0, got {chunk_size}"
            )
        if overlap < 0:
            raise InvalidChunkConfigException(f"overlap must be >= 0, got {overlap}")
        if overlap >= chunk_size:
            raise InvalidChunkConfigException(
                f"overlap ({overlap}) must be less than chunk_size ({chunk_size})"
            )
        if strategy not in _STRATEGY_REGISTRY:
            valid = ", ".join(sorted(_STRATEGY_REGISTRY.keys()))
            raise InvalidChunkConfigException(
                f"Unknown strategy '{strategy}'. Valid options: {valid}"
            )

        self._chunk_size = chunk_size
        self._overlap = overlap
        self._strategy_name = strategy
        self._tokenizer = tokenizer or get_tokenizer()

        strategy_cls = _STRATEGY_REGISTRY[strategy]
        self._strategy: BaseChunkStrategy = strategy_cls(
            chunk_size=chunk_size,
            overlap=overlap,
            tokenizer=self._tokenizer,
        )

    @property
    def strategy_name(self) -> str:
        """Active strategy name."""
        return self._strategy_name

    def chunk(
        self,
        text: str,
        document_id: uuid.UUID | None = None,
        source_filename: str | None = None,
        language: str = "en",
        extra_metadata: dict[str, Any] | None = None,
    ) -> ChunkResult:
        """Synchronously chunk a document text, returning a complete ChunkResult.

        Args:
            text: Full clean document text (from DocumentProcessor.clean_text).
            document_id: Optional parent document UUID.
            source_filename: Optional original filename for metadata.
            language: ISO language code for chunk metadata.
            extra_metadata: Additional attributes to embed in each chunk's metadata.

        Returns:
            ChunkResult: Aggregate container of all generated chunks.
        """
        start_time = time.perf_counter()

        chunks: list[Chunk] = []
        for chunk in self._strategy.chunk(
            text=text,
            document_id=document_id,
            source_filename=source_filename,
            language=language,
            extra_metadata=extra_metadata,
        ):
            chunks.append(chunk)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        total_tokens = sum(c.token_count for c in chunks)

        logger.info(
            "document_chunked",
            document_id=str(document_id) if document_id else None,
            strategy=self._strategy_name,
            chunk_count=len(chunks),
            total_tokens=total_tokens,
            processing_time_ms=round(elapsed_ms, 2),
        )

        return ChunkResult(
            document_id=document_id,
            chunks=chunks,
            total_chunks=len(chunks),
            strategy_used=self._strategy_name,
            chunk_size=self._chunk_size,
            overlap=self._overlap,
            total_tokens=total_tokens,
            processing_time_ms=round(elapsed_ms, 2),
        )

    async def chunk_async(
        self,
        text: str,
        document_id: uuid.UUID | None = None,
        source_filename: str | None = None,
        language: str = "en",
        extra_metadata: dict[str, Any] | None = None,
    ) -> ChunkResult:
        """Asynchronously chunk a document text by offloading to a thread pool.

        Args:
            text: Full clean document text.
            document_id: Optional parent document UUID.
            source_filename: Optional original filename.
            language: ISO language code.
            extra_metadata: Additional chunk metadata attributes.

        Returns:
            ChunkResult: Complete chunking result.
        """
        import asyncio

        return await asyncio.to_thread(
            self.chunk,
            text,
            document_id,
            source_filename,
            language,
            extra_metadata,
        )

    @staticmethod
    def available_strategies() -> list[str]:
        """Return list of all registered chunking strategy names."""
        return sorted(_STRATEGY_REGISTRY.keys())

    @classmethod
    def from_settings(cls) -> ChunkingEngine:
        """Construct a ChunkingEngine from application Settings.

        Returns:
            ChunkingEngine: Engine configured from environment settings.
        """
        from app.core.config import get_settings

        settings = get_settings()
        return cls(
            chunk_size=settings.chunking.chunk_size,
            overlap=settings.chunking.overlap,
            strategy=settings.chunking.strategy,
            tokenizer=get_tokenizer(settings.chunking.tokenizer_encoding),
        )
