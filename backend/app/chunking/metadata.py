"""Chunk Metadata Enrichment Utilities.

Provides helpers to resolve section titles from Markdown headings,
estimate page numbers from character offsets, and build ChunkMetadata instances.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.chunking.models import ChunkMetadata

_MARKDOWN_HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class ChunkMetadataBuilder:
    """Builds page-position and section-title metadata from document structure."""

    def __init__(self, text: str, avg_chars_per_page: int = 3000) -> None:
        """Initialize with full document text.

        Args:
            text: The full clean_text of the source document.
            avg_chars_per_page: Average characters per page for offset-based page estimation.
        """
        self._text = text
        self._avg_chars_per_page = avg_chars_per_page
        self._heading_positions = self._index_headings(text)

    @staticmethod
    def _index_headings(text: str) -> list[tuple[int, int, str]]:
        """Extract all Markdown heading positions (offset, level, title).

        Returns:
            list[tuple[int, int, str]]: Sorted list of (offset, level, title).
        """
        return [
            (m.start(), len(m.group(1)), m.group(2).strip())
            for m in _MARKDOWN_HEADING_REGEX.finditer(text)
        ]

    def resolve_section_title(self, start_offset: int) -> str | None:
        """Find the nearest heading title that precedes the given character offset.

        Args:
            start_offset: Character start offset of the chunk in the full text.

        Returns:
            str | None: Section heading text or None if no headings exist.
        """
        best_title: str | None = None
        for pos, _level, title in self._heading_positions:
            if pos <= start_offset:
                best_title = title
            else:
                break
        return best_title

    def estimate_page_number(self, start_offset: int) -> int | None:
        """Estimate the source page number based on character offset.

        Args:
            start_offset: Character start position of the chunk.

        Returns:
            int | None: 1-indexed estimated page number.
        """
        if self._avg_chars_per_page <= 0:
            return None
        return max(1, (start_offset // self._avg_chars_per_page) + 1)

    def build(
        self,
        chunk_index: int,
        total_chunks: int,
        start_offset: int,
        strategy: str,
        document_id: uuid.UUID | None = None,
        source_filename: str | None = None,
        language: str = "en",
        extra: dict[str, Any] | None = None,
    ) -> ChunkMetadata:
        """Construct a fully-populated ChunkMetadata for a specific chunk.

        Args:
            chunk_index: Zero-based chunk position.
            total_chunks: Total number of chunks in the document.
            start_offset: Character start offset of this chunk.
            strategy: Name of the chunking strategy.
            document_id: Parent document UUID.
            source_filename: Original filename.
            language: ISO language code.
            extra: Extra diagnostic attributes.

        Returns:
            ChunkMetadata: Populated metadata object.
        """
        from app.chunking.models import ChunkMetadata

        return ChunkMetadata(
            document_id=document_id,
            source_filename=source_filename,
            language=language,
            section_title=self.resolve_section_title(start_offset),
            page_number=self.estimate_page_number(start_offset),
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            strategy=strategy,
            extra=extra or {},
        )
