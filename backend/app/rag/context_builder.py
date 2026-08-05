"""Context Builder for Retrieval-Augmented Generation.

Handles deduplication, rank preservation, token budgeting, adaptive text truncation,
source attribution headers, and metadata preservation.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any

from app.core.logging import get_logger
from app.rag.models import BuiltContext, ContextChunk
from app.retrieval.models import RetrievedChunk

logger = get_logger(__name__)

# Token counting support with fallback
_ENCODER: Any = None
try:
    import tiktoken

    _ENCODER = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover
    _ENCODER = None


def count_tokens(text: str) -> int:
    """Count tokens accurately using cl100k_base tokenizer with heuristic fallback."""
    if not text:
        return 0
    if _ENCODER is not None:
        try:
            return len(_ENCODER.encode(text, disallowed_special=()))
        except Exception:
            pass
    return max(1, math.ceil(len(text) / 4))


class ContextFormatter(ABC):
    """Abstract interface for formatting context chunks into prompt text."""

    @abstractmethod
    def format_chunk(
        self,
        source_index: int,
        citation_tag: str,
        chunk: RetrievedChunk,
        text: str,
    ) -> str:
        """Format an individual chunk with metadata header into text."""
        ...

    @abstractmethod
    def combine_chunks(self, formatted_snippets: list[str]) -> str:
        """Combine formatted chunk snippets into unified context text."""
        ...


class DefaultContextFormatter(ContextFormatter):
    """Standard markdown context formatter with source attribution headers."""

    def format_chunk(
        self,
        source_index: int,
        citation_tag: str,
        chunk: RetrievedChunk,
        text: str,
    ) -> str:
        header_parts: list[str] = []
        doc_label = chunk.title or chunk.file_name or str(chunk.document_id)
        header_parts.append(f"Document: {doc_label}")

        if chunk.page_number is not None:
            header_parts.append(f"Page: {chunk.page_number}")
        if chunk.heading:
            header_parts.append(f"Section: {chunk.heading}")
        if chunk.category:
            header_parts.append(f"Category: {chunk.category}")

        header_str = " | ".join(header_parts)
        return f"[{source_index}] Source [{header_str}]\n{text.strip()}"

    def combine_chunks(self, formatted_snippets: list[str]) -> str:
        return "\n\n---\n\n".join(formatted_snippets)


class ContextBuilder:
    """Builds token-budgeted, deduplicated, rank-preserved context for RAG prompts."""

    def __init__(
        self,
        formatter: ContextFormatter | None = None,
        default_token_budget: int = 4000,
        min_chunk_tokens: int = 30,
    ) -> None:
        """Initialize ContextBuilder.

        Args:
            formatter: Formatter strategy for attributing and combining chunks.
            default_token_budget: Default maximum token budget for the context block.
            min_chunk_tokens: Minimum remaining token allowance to attempt adaptive truncation.
        """
        self._formatter = formatter or DefaultContextFormatter()
        self._default_token_budget = default_token_budget
        self._min_chunk_tokens = min_chunk_tokens

    def count_text_tokens(self, text: str) -> int:
        """Estimate or count tokens for a given string."""
        return count_tokens(text)

    def build_context(
        self,
        chunks: list[RetrievedChunk],
        token_budget: int | None = None,
        max_chunks: int | None = None,
    ) -> BuiltContext:
        """Process retrieved chunks into a budget-constrained, formatted context.

        Args:
            chunks: Ranked retrieved chunks from retrieval/fusion stage.
            token_budget: Max token budget (falls back to default_token_budget).
            max_chunks: Optional upper bound on number of chunks included.

        Returns:
            BuiltContext: Structured context with attribution tags and metadata.
        """
        budget = token_budget if token_budget is not None else self._default_token_budget
        if not chunks or budget <= 0:
            return BuiltContext(
                formatted_context="",
                chunks=[],
                total_tokens=0,
                token_budget=budget,
                truncated_chunks_count=0,
                dropped_chunks_count=len(chunks),
            )

        # 1. Deduplicate by chunk_id while preserving top rank
        seen_chunk_ids: set[str] = set()
        deduped_chunks: list[RetrievedChunk] = []
        for c in chunks:
            cid_str = str(c.chunk_id)
            if cid_str not in seen_chunk_ids:
                seen_chunk_ids.add(cid_str)
                deduped_chunks.append(c)

        if max_chunks is not None and max_chunks > 0:
            deduped_chunks = deduped_chunks[:max_chunks]

        included_context_chunks: list[ContextChunk] = []
        formatted_snippets: list[str] = []
        current_tokens = 0
        truncated_count = 0
        dropped_count = 0

        # 2. Iterate through deduplicated chunks within budget
        for idx, chunk in enumerate(deduped_chunks, start=1):
            citation_tag = f"[{idx}]"
            raw_text = chunk.text.strip()
            if not raw_text:
                continue

            # Check full snippet token cost
            full_snippet = self._formatter.format_chunk(
                source_index=idx,
                citation_tag=citation_tag,
                chunk=chunk,
                text=raw_text,
            )
            snippet_tokens = self.count_text_tokens(full_snippet)

            remaining_budget = budget - current_tokens

            if snippet_tokens <= remaining_budget:
                # Fits entirely
                formatted_snippets.append(full_snippet)
                current_tokens += snippet_tokens
                included_context_chunks.append(
                    ContextChunk(
                        source_index=idx,
                        citation_tag=citation_tag,
                        chunk_id=str(chunk.chunk_id),
                        document_id=str(chunk.document_id),
                        chunk_index=chunk.chunk_index,
                        text=raw_text,
                        token_count=snippet_tokens,
                        score=chunk.score,
                        heading=chunk.heading,
                        page_number=chunk.page_number,
                        title=chunk.title,
                        file_name=chunk.file_name,
                        category=chunk.category,
                        tags=chunk.tags,
                        metadata=chunk.metadata,
                    )
                )
            elif remaining_budget >= self._min_chunk_tokens:
                # Adaptively truncate to fit remaining budget
                # Approximate characters to fit remaining budget
                approx_chars = max(100, remaining_budget * 4 - 80)
                truncated_text = raw_text[:approx_chars].rstrip() + "..."
                trunc_snippet = self._formatter.format_chunk(
                    source_index=idx,
                    citation_tag=citation_tag,
                    chunk=chunk,
                    text=truncated_text,
                )
                trunc_tokens = self.count_text_tokens(trunc_snippet)

                if trunc_tokens <= remaining_budget:
                    formatted_snippets.append(trunc_snippet)
                    current_tokens += trunc_tokens
                    truncated_count += 1
                    included_context_chunks.append(
                        ContextChunk(
                            source_index=idx,
                            citation_tag=citation_tag,
                            chunk_id=str(chunk.chunk_id),
                            document_id=str(chunk.document_id),
                            chunk_index=chunk.chunk_index,
                            text=truncated_text,
                            token_count=trunc_tokens,
                            score=chunk.score,
                            heading=chunk.heading,
                            page_number=chunk.page_number,
                            title=chunk.title,
                            file_name=chunk.file_name,
                            category=chunk.category,
                            tags=chunk.tags,
                            metadata=chunk.metadata,
                        )
                    )
                else:
                    dropped_count += 1
                break
            else:
                dropped_count += 1
                break

        # Calculate remaining dropped count
        total_omitted = max(0, len(chunks) - len(included_context_chunks))

        final_context_text = self._formatter.combine_chunks(formatted_snippets)
        total_tokens = self.count_text_tokens(final_context_text)

        logger.info(
            "rag_context_built",
            chunks_included=len(included_context_chunks),
            chunks_total=len(chunks),
            total_tokens=total_tokens,
            budget=budget,
            truncated_count=truncated_count,
        )

        return BuiltContext(
            formatted_context=final_context_text,
            chunks=included_context_chunks,
            total_tokens=total_tokens,
            token_budget=budget,
            truncated_chunks_count=truncated_count,
            dropped_chunks_count=total_omitted,
        )
