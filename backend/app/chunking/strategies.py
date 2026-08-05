"""Chunking Strategy Implementations.

Provides multiple concrete chunking strategies for different document types:
- FixedCharacterChunker: Simple character-boundary splitting.
- RecursiveCharacterChunker: Hierarchical separator splitting with semantic fallback.
- SentenceChunker: Sentence-boundary-aware splitting.
- ParagraphChunker: Paragraph-boundary splitting.
- MarkdownHeaderChunker: Markdown heading-based semantic splitting.
- AdaptiveChunker: Automatic strategy selection based on document type/content.
"""

from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any, ClassVar

from app.chunking.exceptions import EmptyTextException, InvalidChunkConfigException
from app.chunking.models import Chunk, ChunkMetadata
from app.chunking.tokenizer import Tokenizer, get_tokenizer

# ---------------------------------------------------------------------------
# Regex guards for boundary preservation
# ---------------------------------------------------------------------------

# Matches Markdown fenced code blocks: ```...``` or ~~~...~~~
_CODE_BLOCK_REGEX = re.compile(r"(```[\s\S]*?```|~~~[\s\S]*?~~~)", re.MULTILINE)

# Matches Markdown tables (lines starting with |)
_TABLE_BLOCK_REGEX = re.compile(
    r"(\|.+\|\n(?:\|[-:| ]+\|\n)(?:\|.+\|\n)*)", re.MULTILINE
)

# Matches Markdown headings h1-h6
_HEADING_REGEX = re.compile(r"^#{1,6}\s+.+$", re.MULTILINE)

# Matches URLs to avoid splitting them
_URL_REGEX = re.compile(
    r"https?://[^\s\)\]\>\"\']+",
    re.IGNORECASE,
)

# Sentence terminators followed by whitespace
_SENTENCE_END_REGEX = re.compile(r"(?<=[.!?])\s+")

# Paragraph boundaries: one or more blank lines
_PARAGRAPH_REGEX = re.compile(r"\n{2,}")

# Numbered list items
_NUMBERED_LIST_REGEX = re.compile(r"^\d+\.\s", re.MULTILINE)


# ---------------------------------------------------------------------------
# Guard Utilities
# ---------------------------------------------------------------------------


def _find_protected_ranges(text: str) -> list[tuple[int, int]]:
    """Identify character ranges that should not be split across chunk boundaries.

    Covers: fenced code blocks, markdown tables, and inline URLs.

    Args:
        text: Full document text.

    Returns:
        list[tuple[int, int]]: Sorted list of (start, end) protected ranges.
    """
    ranges: list[tuple[int, int]] = []

    for pattern in (_CODE_BLOCK_REGEX, _TABLE_BLOCK_REGEX):
        for m in pattern.finditer(text):
            ranges.append((m.start(), m.end()))

    for m in _URL_REGEX.finditer(text):
        ranges.append((m.start(), m.end()))

    return sorted(ranges, key=lambda r: r[0])


def _is_in_protected_range(
    pos: int,
    protected: list[tuple[int, int]],
) -> bool:
    """Check if a character position falls inside any protected range."""
    for start, end in protected:
        if start < pos < end:
            return True
        if start > pos:
            break
    return False


def _adjust_split_point(
    pos: int,
    text: str,
    protected: list[tuple[int, int]],
    search_back: int = 200,
) -> int:
    """Nudge a split point backward to avoid falling inside a protected range or mid-word.

    Args:
        pos: Proposed character split position.
        text: Full document text.
        protected: Pre-computed protected ranges.
        search_back: Maximum characters to search back for a safe boundary.

    Returns:
        int: Adjusted safe split position.
    """
    if not _is_in_protected_range(pos, protected):
        return pos

    # Search backward for a position outside all protected ranges
    for candidate in range(pos - 1, max(0, pos - search_back), -1):
        if not _is_in_protected_range(candidate, protected):
            # Prefer splitting at whitespace
            if candidate < len(text) and text[candidate] in " \n\t":
                return candidate + 1
    return pos


# ---------------------------------------------------------------------------
# Abstract Base Strategy
# ---------------------------------------------------------------------------


class BaseChunkStrategy(ABC):
    """Abstract interface for all chunking strategy implementations."""

    name: str = "base"

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 64,
        tokenizer: Tokenizer | None = None,
    ) -> None:
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
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._tokenizer = tokenizer or get_tokenizer()

    def _build_chunk(
        self,
        text_slice: str,
        document_id: uuid.UUID | None,
        chunk_index: int,
        start_offset: int,
        end_offset: int,
        metadata: ChunkMetadata,
    ) -> Chunk:
        """Construct a fully-populated Chunk from a text slice."""
        stripped = text_slice.strip()
        return Chunk(
            chunk_id=Chunk.compute_chunk_id(document_id, chunk_index, stripped),
            document_id=document_id,
            chunk_index=chunk_index,
            text=stripped,
            start_offset=start_offset,
            end_offset=end_offset,
            token_count=self._tokenizer.count_tokens(stripped),
            character_count=len(stripped),
            section_title=metadata.section_title,
            page_number=metadata.page_number,
            checksum=Chunk.compute_checksum(stripped),
            metadata=metadata,
        )

    @abstractmethod
    def chunk(
        self,
        text: str,
        document_id: uuid.UUID | None = None,
        source_filename: str | None = None,
        language: str = "en",
        extra_metadata: dict[str, Any] | None = None,
    ) -> Generator[Chunk, None, None]:
        """Generate chunks from the given document text.

        Args:
            text: Full clean document text.
            document_id: Parent document UUID.
            source_filename: Original document filename.
            language: Document language code.
            extra_metadata: Additional context attributes.

        Yields:
            Chunk: Generated text chunks in order.
        """
        ...

    def _validate_text(self, text: str) -> str:
        """Validate and strip input text, raising EmptyTextException if empty."""
        stripped = text.strip()
        if not stripped:
            raise EmptyTextException()
        return stripped


# ---------------------------------------------------------------------------
# Strategy 1: Fixed Character
# ---------------------------------------------------------------------------


class FixedCharacterChunker(BaseChunkStrategy):
    """Split text into fixed character-size windows with token-counted overlap.

    Best for: uniformly formatted plaintext, logs, CSV exports.
    """

    name = "fixed_character"

    def chunk(
        self,
        text: str,
        document_id: uuid.UUID | None = None,
        source_filename: str | None = None,
        language: str = "en",
        extra_metadata: dict[str, Any] | None = None,
    ) -> Generator[Chunk, None, None]:
        """Yield chunks using fixed character windows with overlap."""
        from app.chunking.metadata import ChunkMetadataBuilder

        clean = self._validate_text(text)
        protected = _find_protected_ranges(clean)
        builder = ChunkMetadataBuilder(clean)

        # Estimate character window from token budget
        # Use a running estimate: tokens ≈ chars / 4
        char_window = self._chunk_size * 4
        char_overlap = self._overlap * 4

        text_len = len(clean)

        # Two-pass approach: collect split boundaries first, then emit chunks
        # to allow accurate total_chunks for metadata
        split_points: list[tuple[int, int]] = []

        pos = 0
        while pos < text_len:
            end = min(pos + char_window, text_len)

            if end < text_len:
                # Try to snap to whitespace boundary
                safe_end = end
                for char_pos in range(min(end + 50, text_len), max(pos, end - 100), -1):
                    if char_pos < text_len and clean[char_pos] in "\n ":
                        if not _is_in_protected_range(char_pos, protected):
                            safe_end = char_pos + 1
                            break
                end = safe_end

            slice_text = clean[pos:end].strip()
            if slice_text:
                split_points.append((pos, end))
            pos = max(pos + 1, end - char_overlap)

        total = len(split_points)
        for i, (s, e) in enumerate(split_points):
            slice_text = clean[s:e].strip()
            if not slice_text:
                continue
            meta = builder.build(
                chunk_index=i,
                total_chunks=total,
                start_offset=s,
                strategy=self.name,
                document_id=document_id,
                source_filename=source_filename,
                language=language,
                extra=extra_metadata or {},
            )
            yield self._build_chunk(slice_text, document_id, i, s, e, meta)


# ---------------------------------------------------------------------------
# Strategy 2: Recursive Character
# ---------------------------------------------------------------------------


class RecursiveCharacterChunker(BaseChunkStrategy):
    """Hierarchical separator-based splitting with semantic fallback.

    Attempts to split at: paragraph breaks → sentence ends → word boundaries.
    Best for: prose documents, reports, structured plaintext.
    """

    name = "recursive_character"

    _SEPARATORS: ClassVar[tuple[str, ...]] = ("\n\n", "\n", ". ", "! ", "? ", " ", "")

    def chunk(
        self,
        text: str,
        document_id: uuid.UUID | None = None,
        source_filename: str | None = None,
        language: str = "en",
        extra_metadata: dict[str, Any] | None = None,
    ) -> Generator[Chunk, None, None]:
        """Yield chunks using hierarchical separator splitting."""
        from app.chunking.metadata import ChunkMetadataBuilder

        clean = self._validate_text(text)
        builder = ChunkMetadataBuilder(clean)
        protected = _find_protected_ranges(clean)

        segments = self._recursive_split(clean, protected)

        total = len(segments)
        for i, (s, e, segment_text) in enumerate(segments):
            if not segment_text.strip():
                continue
            meta = builder.build(
                chunk_index=i,
                total_chunks=total,
                start_offset=s,
                strategy=self.name,
                document_id=document_id,
                source_filename=source_filename,
                language=language,
                extra=extra_metadata or {},
            )
            yield self._build_chunk(segment_text, document_id, i, s, e, meta)

    def _recursive_split(
        self,
        text: str,
        protected: list[tuple[int, int]],
    ) -> list[tuple[int, int, str]]:
        """Recursively split text segments respecting token limits and protected ranges."""
        max_chars = self._chunk_size * 4
        overlap_chars = self._overlap * 4
        results: list[tuple[int, int, str]] = []

        segments = self._split_with_separators(text, protected)
        current_start = 0
        current_chunks: list[str] = []
        current_chars = 0

        for segment in segments:
            seg_len = len(segment)
            if current_chars + seg_len > max_chars and current_chunks:
                # Emit current accumulation
                combined = " ".join(current_chunks)
                results.append((current_start, current_start + len(combined), combined))
                # Compute overlap carryover
                overlap_text = combined[-overlap_chars:] if overlap_chars > 0 else ""
                current_start = current_start + len(combined) - len(overlap_text)
                current_chunks = [overlap_text] if overlap_text else []
                current_chars = len(overlap_text)

            current_chunks.append(segment)
            current_chars += seg_len

        if current_chunks:
            combined = " ".join(current_chunks)
            results.append((current_start, current_start + len(combined), combined))

        return results

    def _split_with_separators(
        self,
        text: str,
        protected: list[tuple[int, int]],
    ) -> list[str]:
        """Split text by priority separators, skipping protected regions."""
        for sep in self._SEPARATORS:
            if not sep:
                continue
            if sep in text:
                parts = text.split(sep)
                non_empty = [p for p in parts if p.strip()]
                if len(non_empty) > 1:
                    return non_empty

        return [text]


# ---------------------------------------------------------------------------
# Strategy 3: Sentence Based
# ---------------------------------------------------------------------------


class SentenceChunker(BaseChunkStrategy):
    """Accumulate sentences until token budget exhausted, then emit chunk with overlap.

    Best for: narrative prose, research papers, interview transcripts.
    """

    name = "sentence"

    def chunk(
        self,
        text: str,
        document_id: uuid.UUID | None = None,
        source_filename: str | None = None,
        language: str = "en",
        extra_metadata: dict[str, Any] | None = None,
    ) -> Generator[Chunk, None, None]:
        """Yield sentence-boundary chunks."""
        from app.chunking.metadata import ChunkMetadataBuilder

        clean = self._validate_text(text)
        builder = ChunkMetadataBuilder(clean)

        sentences = self._split_sentences(clean)
        if not sentences:
            return

        # Build token-sized windows of sentences
        windows = self._build_windows(sentences)
        total = len(windows)

        char_pos = 0
        for i, window_text in enumerate(windows):
            start = clean.find(window_text, char_pos)
            if start == -1:
                start = char_pos
            end = start + len(window_text)
            char_pos = max(char_pos, end - self._overlap * 4)

            meta = builder.build(
                chunk_index=i,
                total_chunks=total,
                start_offset=start,
                strategy=self.name,
                document_id=document_id,
                source_filename=source_filename,
                language=language,
                extra=extra_metadata or {},
            )
            yield self._build_chunk(window_text, document_id, i, start, end, meta)

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into individual sentences preserving terminating whitespace."""
        raw_sentences = _SENTENCE_END_REGEX.split(text)
        result = []
        for s in raw_sentences:
            stripped = s.strip()
            if stripped:
                result.append(stripped)
        return result

    def _build_windows(self, sentences: list[str]) -> list[str]:
        """Accumulate sentences into windows bounded by the token budget."""
        windows: list[str] = []
        current: list[str] = []
        current_tokens = 0
        overlap_sentences: list[str] = []

        for sentence in sentences:
            sentence_tokens = self._tokenizer.count_tokens(sentence)
            if current_tokens + sentence_tokens > self._chunk_size and current:
                windows.append(" ".join(current))
                # Compute overlap from tail sentences
                overlap_tokens = 0
                overlap_sentences = []
                for sent in reversed(current):
                    t = self._tokenizer.count_tokens(sent)
                    if overlap_tokens + t <= self._overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_tokens += t
                    else:
                        break
                current = list(overlap_sentences)
                current_tokens = sum(self._tokenizer.count_tokens(s) for s in current)

            current.append(sentence)
            current_tokens += sentence_tokens

        if current:
            windows.append(" ".join(current))

        return windows


# ---------------------------------------------------------------------------
# Strategy 4: Paragraph Based
# ---------------------------------------------------------------------------


class ParagraphChunker(BaseChunkStrategy):
    """Split document on paragraph boundaries, accumulating into token-bounded windows.

    Best for: documents with clear paragraph structure — README files, wiki articles.
    """

    name = "paragraph"

    def chunk(
        self,
        text: str,
        document_id: uuid.UUID | None = None,
        source_filename: str | None = None,
        language: str = "en",
        extra_metadata: dict[str, Any] | None = None,
    ) -> Generator[Chunk, None, None]:
        """Yield paragraph-bounded chunks."""
        from app.chunking.metadata import ChunkMetadataBuilder

        clean = self._validate_text(text)
        builder = ChunkMetadataBuilder(clean)

        paragraphs = [p.strip() for p in _PARAGRAPH_REGEX.split(clean) if p.strip()]
        if not paragraphs:
            return

        windows = self._build_windows(paragraphs)
        total = len(windows)

        char_pos = 0
        for i, window_text in enumerate(windows):
            start = clean.find(window_text.split("\n\n")[0].strip(), char_pos)
            if start == -1:
                start = char_pos
            end = start + len(window_text)
            char_pos = max(char_pos + 1, end - self._overlap * 4)

            meta = builder.build(
                chunk_index=i,
                total_chunks=total,
                start_offset=start,
                strategy=self.name,
                document_id=document_id,
                source_filename=source_filename,
                language=language,
                extra=extra_metadata or {},
            )
            yield self._build_chunk(window_text, document_id, i, start, end, meta)

    def _build_windows(self, paragraphs: list[str]) -> list[str]:
        """Accumulate paragraphs into token-bounded windows."""
        windows: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for paragraph in paragraphs:
            para_tokens = self._tokenizer.count_tokens(paragraph)

            if current_tokens + para_tokens > self._chunk_size and current:
                windows.append("\n\n".join(current))
                # Overlap: carry last paragraph if it fits
                last = current[-1]
                last_tokens = self._tokenizer.count_tokens(last)
                if last_tokens <= self._overlap:
                    current = [last]
                    current_tokens = last_tokens
                else:
                    current = []
                    current_tokens = 0

            current.append(paragraph)
            current_tokens += para_tokens

        if current:
            windows.append("\n\n".join(current))

        return windows


# ---------------------------------------------------------------------------
# Strategy 5: Markdown Header Based
# ---------------------------------------------------------------------------


class MarkdownHeaderChunker(BaseChunkStrategy):
    """Split Markdown documents at heading boundaries, preserving semantic sections.

    Best for: Markdown documentation, wikis, runbooks with clear heading structure.
    """

    name = "markdown_header"

    def chunk(
        self,
        text: str,
        document_id: uuid.UUID | None = None,
        source_filename: str | None = None,
        language: str = "en",
        extra_metadata: dict[str, Any] | None = None,
    ) -> Generator[Chunk, None, None]:
        """Yield chunks split at Markdown heading boundaries."""
        from app.chunking.metadata import ChunkMetadataBuilder

        clean = self._validate_text(text)
        builder = ChunkMetadataBuilder(clean)

        sections = self._split_at_headings(clean)
        if not sections:
            return

        total = len(sections)
        for i, (start, end, title, section_text) in enumerate(sections):
            if not section_text.strip():
                continue
            meta = builder.build(
                chunk_index=i,
                total_chunks=total,
                start_offset=start,
                strategy=self.name,
                document_id=document_id,
                source_filename=source_filename,
                language=language,
                extra=extra_metadata or {},
            )
            # Override section title with the heading we found
            from app.chunking.models import ChunkMetadata

            meta = ChunkMetadata(
                **{**meta.model_dump(), "section_title": title or meta.section_title}
            )
            yield self._build_chunk(section_text, document_id, i, start, end, meta)

    def _split_at_headings(
        self,
        text: str,
    ) -> list[tuple[int, int, str | None, str]]:
        """Split text into sections delimited by Markdown headings.

        Returns:
            list[tuple[int, int, str | None, str]]: (start, end, title, section_text).
        """
        heading_matches = list(_HEADING_REGEX.finditer(text))
        if not heading_matches:
            # No headings — return whole text as one section
            return [(0, len(text), None, text)]

        sections: list[tuple[int, int, str | None, str]] = []

        # Text before first heading
        if heading_matches[0].start() > 0:
            preamble = text[: heading_matches[0].start()].strip()
            if preamble:
                sections.append((0, heading_matches[0].start(), None, preamble))

        for idx, match in enumerate(heading_matches):
            start = match.start()
            end = (
                heading_matches[idx + 1].start()
                if idx + 1 < len(heading_matches)
                else len(text)
            )
            title = re.sub(r"^#+\s*", "", match.group(0)).strip()
            section_text = text[start:end].strip()

            # If section is too long, sub-split it
            if self._tokenizer.count_tokens(section_text) > self._chunk_size:
                sub_chunks = self._sub_split(section_text, start)
                sections.extend(sub_chunks)
            else:
                sections.append((start, end, title, section_text))

        return sections

    def _sub_split(
        self,
        text: str,
        base_offset: int,
    ) -> list[tuple[int, int, str | None, str]]:
        """Sub-split an oversized section using paragraph boundaries."""
        results: list[tuple[int, int, str | None, str]] = []
        paragraphs = [p.strip() for p in _PARAGRAPH_REGEX.split(text) if p.strip()]
        current: list[str] = []
        current_tokens = 0
        rel_pos = 0

        for para in paragraphs:
            tokens = self._tokenizer.count_tokens(para)
            if current_tokens + tokens > self._chunk_size and current:
                combined = "\n\n".join(current)
                results.append(
                    (
                        base_offset + rel_pos,
                        base_offset + rel_pos + len(combined),
                        None,
                        combined,
                    )
                )
                rel_pos += len(combined) + 2
                current = []
                current_tokens = 0
            current.append(para)
            current_tokens += tokens

        if current:
            combined = "\n\n".join(current)
            results.append(
                (
                    base_offset + rel_pos,
                    base_offset + rel_pos + len(combined),
                    None,
                    combined,
                )
            )

        return results


# ---------------------------------------------------------------------------
# Strategy 6: Adaptive
# ---------------------------------------------------------------------------


class AdaptiveChunker(BaseChunkStrategy):
    """Automatically select the optimal chunking strategy based on document structure.

    Selection heuristics (in priority order):
    1. If ≥ 3 Markdown headings → MarkdownHeaderChunker
    2. If ≥ 5 paragraphs → ParagraphChunker
    3. If ≥ 10 sentences → SentenceChunker
    4. Otherwise → RecursiveCharacterChunker
    """

    name = "adaptive"

    def chunk(
        self,
        text: str,
        document_id: uuid.UUID | None = None,
        source_filename: str | None = None,
        language: str = "en",
        extra_metadata: dict[str, Any] | None = None,
    ) -> Generator[Chunk, None, None]:
        """Detect the best strategy and delegate to it."""
        clean = self._validate_text(text)
        selected = self._select_strategy(clean)

        strategy_extra = extra_metadata or {}
        strategy_extra = {**strategy_extra, "adaptive_selected": selected.name}

        yield from selected.chunk(
            text=clean,
            document_id=document_id,
            source_filename=source_filename,
            language=language,
            extra_metadata=strategy_extra,
        )

    def _select_strategy(self, text: str) -> BaseChunkStrategy:
        """Heuristically select the most appropriate chunking strategy."""
        cs = self._chunk_size
        ov = self._overlap
        tok = self._tokenizer

        heading_count = len(list(_HEADING_REGEX.finditer(text)))
        if heading_count >= 3:
            return MarkdownHeaderChunker(chunk_size=cs, overlap=ov, tokenizer=tok)

        paragraph_count = len([p for p in _PARAGRAPH_REGEX.split(text) if p.strip()])
        if paragraph_count >= 5:
            return ParagraphChunker(chunk_size=cs, overlap=ov, tokenizer=tok)

        sentence_count = len(_SENTENCE_END_REGEX.split(text))
        if sentence_count >= 10:
            return SentenceChunker(chunk_size=cs, overlap=ov, tokenizer=tok)

        return RecursiveCharacterChunker(chunk_size=cs, overlap=ov, tokenizer=tok)

    @property
    def selected_strategy_name(self) -> str:
        """Return a descriptive label for diagnostic purposes."""
        return "adaptive (auto-select)"
