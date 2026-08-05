"""Citation Extraction and Source Attribution Engine.

Identifies citations in generated LLM responses, correlates source references with
context chunks, resolves metadata, and builds structured Citation objects.
"""

from __future__ import annotations

import re
from re import Pattern
from typing import ClassVar

from app.rag.models import BuiltContext, Citation, ContextChunk


class CitationExtractor:
    """Independent citation extractor supporting multiple citation formats."""

    # Regex patterns for matching various citation styles:
    # 1. Standard bracketed numbers: [1], [2], [12]
    # 2. Multi-citations: [1, 2], [1, 3, 5]
    # 3. Source tags: [Source 1], [source 2]
    CITATION_PATTERNS: ClassVar[list[Pattern[str]]] = [
        re.compile(r"\[(?:Source\s*)?(\d+(?:\s*,\s*\d+)*)\]", re.IGNORECASE),
        re.compile(r"\[(\d+)\]"),
    ]

    def extract_citations(
        self,
        text: str,
        context: BuiltContext,
    ) -> list[Citation]:
        """Extract citations from response text and correlate with context chunks.

        Args:
            text: LLM generated answer text containing citation markers.
            context: Built context object with indexed context chunks.

        Returns:
            list[Citation]: Deduplicated, ordered list of verified citations.
        """
        if not text or not context.chunks:
            return []

        # Map source_index -> ContextChunk
        chunk_map: dict[int, ContextChunk] = {
            chunk.source_index: chunk for chunk in context.chunks
        }

        found_indices: set[int] = set()

        for pattern in self.CITATION_PATTERNS:
            for match in pattern.finditer(text):
                raw_group = match.group(1)
                # Split comma-separated citations if present (e.g. "1, 2")
                parts = raw_group.split(",")
                for p in parts:
                    clean_str = p.strip()
                    if clean_str.isdigit():
                        idx = int(clean_str)
                        if idx in chunk_map:
                            found_indices.add(idx)

        # Build Citation DTOs ordered by citation index
        citations: list[Citation] = []
        for idx in sorted(found_indices):
            chunk = chunk_map[idx]

            # Snippet: first 250 chars of chunk text
            snippet = chunk.text.strip()
            if len(snippet) > 250:
                snippet = snippet[:247] + "..."

            # Normalize confidence score
            confidence = min(1.0, max(0.1, chunk.score if chunk.score <= 1.0 else (1.0 / (1.0 + chunk.score))))

            citation = Citation(
                source_index=idx,
                citation_tag=f"[{idx}]",
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                title=chunk.title,
                file_name=chunk.file_name,
                page_number=chunk.page_number,
                heading=chunk.heading,
                category=chunk.category,
                score=chunk.score,
                relevance_confidence=round(confidence, 4),
                snippet=snippet,
            )
            citations.append(citation)

        return citations
