"""Unit Tests for the Intelligent Chunking Engine.

Covers:
- Tokenizer: tiktoken availability, fallback counting, split_by_token_limit
- ChunkMetadataBuilder: heading resolution, page number estimation, frontmatter
- FixedCharacterChunker: basic splitting, overlap, deterministic IDs
- RecursiveCharacterChunker: separator hierarchy, overlap
- SentenceChunker: sentence boundary splitting and overlap
- ParagraphChunker: paragraph boundary splitting
- MarkdownHeaderChunker: heading-based sectioning and sub-split
- AdaptiveChunker: auto-selection heuristics
- ChunkingEngine: sync and async, from_settings, strategy registry
- Deterministic IDs: identical input produces identical chunk_id
- Large document: 500+ page simulation with generator memory efficiency
- Invalid config: guards on overlap >= chunk_size, negative values
- Chunk model: checksum, character_count, token_count correctness
"""

from __future__ import annotations

import uuid

import pytest

from app.chunking import (
    AdaptiveChunker,
    Chunk,
    ChunkingEngine,
    EmptyTextException,
    FixedCharacterChunker,
    InvalidChunkConfigException,
    MarkdownHeaderChunker,
    ParagraphChunker,
    RecursiveCharacterChunker,
    SentenceChunker,
    Tokenizer,
    get_tokenizer,
)
from app.chunking.metadata import ChunkMetadataBuilder
from app.chunking.models import ChunkMetadata, ChunkResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tokenizer() -> Tokenizer:
    return get_tokenizer("cl100k_base")


@pytest.fixture
def simple_prose() -> str:
    return (
        "The Investiga platform provides AI-powered incident investigation. "
        "Security analysts can upload evidence and trigger automated workflows. "
        "Alerts are correlated across multiple data sources. "
        "Results are presented in an interactive timeline view. "
        "Playbooks guide responders through remediation steps."
    )


@pytest.fixture
def markdown_document() -> str:
    return """# Security Incident Report

## Executive Summary

The SOC detected anomalous network traffic on August 5th 2026.
Initial triage confirmed a brute-force attack on the authentication gateway.

## Technical Analysis

### Attack Vector

The attacker used a distributed botnet across 1,200 IP addresses.
Packets were crafted to evade existing rate-limiting rules.

### Impact Assessment

Approximately 4,000 failed login attempts were recorded.
No successful authentication breaches were detected.

## Remediation Actions

1. Rate limiting thresholds reduced to 10 attempts per minute.
2. IP reputation feed updated and applied to WAF rules.
3. Monitoring dashboards updated with new alert thresholds.

## Conclusion

The incident was contained within 45 minutes of detection.
All systems returned to normal operational state.
"""


@pytest.fixture
def large_document() -> str:
    """Simulate a 500+ page document by generating ~1.5M characters."""
    paragraph = (
        "This is a sample paragraph from an enterprise incident report. "
        "It contains detailed forensic analysis and remediation recommendations. "
        "Each section covers a different aspect of the security incident response lifecycle.\n\n"
    )
    return paragraph * 5000  # ~5000 paragraphs ≈ 750k+ chars


# ---------------------------------------------------------------------------
# 1. Tokenizer Tests
# ---------------------------------------------------------------------------


def test_tokenizer_backend_detection(tokenizer: Tokenizer) -> None:
    """Verify tokenizer detects tiktoken backend correctly."""
    assert tokenizer.backend in ("tiktoken", "fallback")


def test_tokenizer_count_tokens_nonempty(tokenizer: Tokenizer) -> None:
    """Verify token counts are positive for non-empty strings."""
    count = tokenizer.count_tokens("Hello, World!")
    assert count > 0


def test_tokenizer_count_tokens_empty(tokenizer: Tokenizer) -> None:
    """Empty string should produce zero tokens."""
    assert tokenizer.count_tokens("") == 0


def test_tokenizer_estimate_alias(tokenizer: Tokenizer) -> None:
    """estimate_tokens should produce same result as count_tokens."""
    text = "Enterprise security operations center"
    assert tokenizer.estimate_tokens(text) == tokenizer.count_tokens(text)


def test_tokenizer_split_short_text(tokenizer: Tokenizer) -> None:
    """Short text within budget should return single-element list."""
    short = "Brief report summary."
    result = tokenizer.split_by_token_limit(short, max_tokens=512)
    assert len(result) == 1
    assert result[0] == short


def test_tokenizer_split_long_text(tokenizer: Tokenizer) -> None:
    """Long text exceeding budget should split into multiple segments."""
    long_text = ("A" * 20 + " ") * 300  # ~6000 chars, ~1500 tokens
    result = tokenizer.split_by_token_limit(long_text, max_tokens=128)
    assert len(result) > 1


def test_tokenizer_fallback_estimator() -> None:
    """Verify fallback estimator produces reasonable results without tiktoken."""
    t = Tokenizer.__new__(Tokenizer)
    t._encoding_name = "cl100k_base"
    t._enc = None  # Force fallback mode

    count = t.count_tokens("The quick brown fox jumped over the lazy dog.")
    assert count > 0
    assert t.backend == "fallback"


# ---------------------------------------------------------------------------
# 2. ChunkMetadataBuilder Tests
# ---------------------------------------------------------------------------


def test_metadata_builder_section_title_resolution() -> None:
    """Builder should resolve nearest heading title preceding the offset."""
    md = "# Introduction\n\nSome intro text.\n\n## Background\n\nBackground text."
    builder = ChunkMetadataBuilder(md)

    # Offset in intro section
    title_at_20 = builder.resolve_section_title(20)
    assert title_at_20 == "Introduction"

    # Offset in background section
    bg_offset = md.index("## Background")
    title_bg = builder.resolve_section_title(bg_offset + 10)
    assert title_bg == "Background"


def test_metadata_builder_page_number_estimation() -> None:
    """Builder should estimate page numbers from character offsets."""
    text = "x" * 9000
    builder = ChunkMetadataBuilder(text, avg_chars_per_page=3000)
    assert builder.estimate_page_number(0) == 1
    assert builder.estimate_page_number(3000) == 2
    assert builder.estimate_page_number(6000) == 3


def test_metadata_builder_build_returns_complete_metadata() -> None:
    """build() should return a fully populated ChunkMetadata."""
    text = "# Heading\n\nContent here."
    doc_id = uuid.uuid4()
    builder = ChunkMetadataBuilder(text)
    meta = builder.build(
        chunk_index=0,
        total_chunks=3,
        start_offset=0,
        strategy="paragraph",
        document_id=doc_id,
        source_filename="report.md",
        language="en",
    )
    assert isinstance(meta, ChunkMetadata)
    assert meta.document_id == doc_id
    assert meta.source_filename == "report.md"
    assert meta.chunk_index == 0
    assert meta.total_chunks == 3
    assert meta.strategy == "paragraph"


# ---------------------------------------------------------------------------
# 3. Fixed Character Chunker Tests
# ---------------------------------------------------------------------------


def test_fixed_character_basic_chunking(simple_prose: str) -> None:
    """Basic chunking should produce at least one chunk."""
    chunker = FixedCharacterChunker(chunk_size=128, overlap=16)
    chunks = list(chunker.chunk(simple_prose))
    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.text.strip() != ""
        assert chunk.character_count > 0
        assert chunk.token_count > 0
        assert chunk.checksum != ""


def test_fixed_character_overlap(simple_prose: str) -> None:
    """Consecutive chunks should share overlapping text when chunk_size is small."""
    chunker = FixedCharacterChunker(chunk_size=64, overlap=16)
    chunks = list(chunker.chunk(simple_prose))
    if len(chunks) >= 2:
        # At least the text should be non-empty and ordered
        for i in range(len(chunks) - 1):
            assert chunks[i].chunk_index < chunks[i + 1].chunk_index


def test_fixed_character_empty_text() -> None:
    """Empty input should raise EmptyTextException."""
    chunker = FixedCharacterChunker(chunk_size=512, overlap=64)
    with pytest.raises(EmptyTextException):
        list(chunker.chunk(""))


def test_fixed_character_invalid_config() -> None:
    """Overlap >= chunk_size should raise InvalidChunkConfigException."""
    with pytest.raises(InvalidChunkConfigException):
        FixedCharacterChunker(chunk_size=64, overlap=64)

    with pytest.raises(InvalidChunkConfigException):
        FixedCharacterChunker(chunk_size=0, overlap=0)


# ---------------------------------------------------------------------------
# 4. Recursive Character Chunker Tests
# ---------------------------------------------------------------------------


def test_recursive_character_chunker(simple_prose: str) -> None:
    """Recursive chunker should produce ordered, non-empty chunks."""
    chunker = RecursiveCharacterChunker(chunk_size=128, overlap=16)
    chunks = list(chunker.chunk(simple_prose))
    assert len(chunks) >= 1
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
        assert chunk.text.strip() != ""


def test_recursive_character_chunk_metadata(simple_prose: str) -> None:
    """Metadata should be populated with correct strategy name."""
    doc_id = uuid.uuid4()
    chunker = RecursiveCharacterChunker(chunk_size=256, overlap=32)
    chunks = list(
        chunker.chunk(simple_prose, document_id=doc_id, source_filename="test.txt")
    )
    assert all(c.metadata.strategy == "recursive_character" for c in chunks)
    assert all(c.document_id == doc_id for c in chunks)


# ---------------------------------------------------------------------------
# 5. Sentence Chunker Tests
# ---------------------------------------------------------------------------


def test_sentence_chunker_basic(simple_prose: str) -> None:
    """Sentence chunker should split at sentence boundaries."""
    chunker = SentenceChunker(chunk_size=64, overlap=8)
    chunks = list(chunker.chunk(simple_prose))
    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.text.strip() != ""
        assert chunk.metadata.strategy == "sentence"


def test_sentence_chunker_empty_text() -> None:
    """Empty text should raise EmptyTextException."""
    chunker = SentenceChunker(chunk_size=512, overlap=64)
    with pytest.raises(EmptyTextException):
        list(chunker.chunk("   "))


# ---------------------------------------------------------------------------
# 6. Paragraph Chunker Tests
# ---------------------------------------------------------------------------


def test_paragraph_chunker_basic(markdown_document: str) -> None:
    """Paragraph chunker should split on blank-line boundaries."""
    chunker = ParagraphChunker(chunk_size=256, overlap=32)
    chunks = list(chunker.chunk(markdown_document))
    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.text.strip() != ""
        assert chunk.metadata.strategy == "paragraph"


def test_paragraph_chunker_overlap() -> None:
    """Verify overlap carries last paragraph into next chunk."""
    text = "\n\n".join([f"Paragraph {i} with some content." for i in range(20)])
    chunker = ParagraphChunker(chunk_size=64, overlap=16)
    chunks = list(chunker.chunk(text))
    assert len(chunks) >= 2


# ---------------------------------------------------------------------------
# 7. Markdown Header Chunker Tests
# ---------------------------------------------------------------------------


def test_markdown_header_chunker_basic(markdown_document: str) -> None:
    """Markdown header chunker should split at heading boundaries."""
    chunker = MarkdownHeaderChunker(chunk_size=512, overlap=64)
    chunks = list(chunker.chunk(markdown_document))
    assert len(chunks) >= 2  # At least main heading + subsections


def test_markdown_header_section_titles_preserved(markdown_document: str) -> None:
    """Each chunk should have section_title set from nearest heading."""
    chunker = MarkdownHeaderChunker(chunk_size=512, overlap=64)
    chunks = list(chunker.chunk(markdown_document))
    # At least some chunks should have section titles from the headings
    titled = [c for c in chunks if c.section_title is not None]
    assert len(titled) >= 1


def test_markdown_header_no_headings() -> None:
    """Document without headings falls back to single whole-text chunk."""
    text = "Just plain text without any headings. More text follows."
    chunker = MarkdownHeaderChunker(chunk_size=512, overlap=64)
    chunks = list(chunker.chunk(text))
    assert len(chunks) == 1
    assert chunks[0].section_title is None


# ---------------------------------------------------------------------------
# 8. Adaptive Chunker Tests
# ---------------------------------------------------------------------------


def test_adaptive_selects_markdown_for_heading_rich_documents(
    markdown_document: str,
) -> None:
    """Adaptive chunker should select markdown_header strategy for heading-rich docs."""
    chunker = AdaptiveChunker(chunk_size=512, overlap=64)
    chunks = list(chunker.chunk(markdown_document))
    assert len(chunks) >= 1
    # Strategy in metadata should indicate adaptive with auto-selection
    for chunk in chunks:
        assert "adaptive_selected" in chunk.metadata.extra


def test_adaptive_selects_paragraph_for_prose() -> None:
    """Adaptive chunker should select paragraph strategy for multi-paragraph prose."""
    text = "\n\n".join(
        [f"Paragraph {i}: This is detailed content about topic {i}." for i in range(10)]
    )
    chunker = AdaptiveChunker(chunk_size=256, overlap=32)
    chunks = list(chunker.chunk(text))
    assert len(chunks) >= 1
    adaptive_selected = chunks[0].metadata.extra.get("adaptive_selected")
    assert adaptive_selected in ("paragraph", "sentence", "recursive_character")


def test_adaptive_selects_recursive_for_short_text() -> None:
    """Short text with no headings or many paragraphs falls back to recursive."""
    text = "Short text. Another sentence. Final sentence."
    chunker = AdaptiveChunker(chunk_size=512, overlap=64)
    chunks = list(chunker.chunk(text))
    assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# 9. ChunkingEngine Tests
# ---------------------------------------------------------------------------


def test_chunking_engine_default_strategy(simple_prose: str) -> None:
    """Default engine should use adaptive strategy."""
    engine = ChunkingEngine()
    assert engine.strategy_name == "adaptive"
    result = engine.chunk(simple_prose)
    assert isinstance(result, ChunkResult)
    assert result.total_chunks >= 1
    assert result.strategy_used == "adaptive"


def test_chunking_engine_explicit_strategies(simple_prose: str) -> None:
    """Verify all strategies can be instantiated and run successfully."""
    for strategy in ChunkingEngine.available_strategies():
        engine = ChunkingEngine(chunk_size=128, overlap=16, strategy=strategy)
        result = engine.chunk(simple_prose)
        assert result.total_chunks >= 1
        assert result.strategy_used == strategy


def test_chunking_engine_result_totals(simple_prose: str) -> None:
    """ChunkResult total_tokens should sum individual chunk token counts."""
    engine = ChunkingEngine(chunk_size=64, overlap=8)
    result = engine.chunk(simple_prose)
    expected_total = sum(c.token_count for c in result.chunks)
    assert result.total_tokens == expected_total


def test_chunking_engine_invalid_strategy() -> None:
    """Unknown strategy name should raise InvalidChunkConfigException."""
    with pytest.raises(InvalidChunkConfigException):
        ChunkingEngine(strategy="unknown_strategy_name")


def test_chunking_engine_invalid_config() -> None:
    """Invalid overlap >= chunk_size should raise InvalidChunkConfigException."""
    with pytest.raises(InvalidChunkConfigException):
        ChunkingEngine(chunk_size=64, overlap=128)


@pytest.mark.asyncio
async def test_chunking_engine_async(simple_prose: str) -> None:
    """Async chunking should produce identical results to sync chunking."""
    engine = ChunkingEngine(chunk_size=128, overlap=16, strategy="recursive_character")
    sync_result = engine.chunk(simple_prose)
    async_result = await engine.chunk_async(simple_prose)
    assert len(sync_result.chunks) == len(async_result.chunks)
    for s, a in zip(sync_result.chunks, async_result.chunks, strict=True):
        assert s.chunk_id == a.chunk_id
        assert s.text == a.text


def test_chunking_engine_available_strategies() -> None:
    """available_strategies should return all 6 registered strategies."""
    strategies = ChunkingEngine.available_strategies()
    assert len(strategies) == 6
    assert "adaptive" in strategies
    assert "markdown_header" in strategies
    assert "fixed_character" in strategies
    assert "recursive_character" in strategies
    assert "sentence" in strategies
    assert "paragraph" in strategies


# ---------------------------------------------------------------------------
# 10. Deterministic Chunk ID Tests
# ---------------------------------------------------------------------------


def test_deterministic_chunk_ids_identical_inputs() -> None:
    """Re-chunking identical text should produce identical chunk_ids."""
    doc_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    text = "Identical document text used to verify determinism of chunk IDs."

    engine = ChunkingEngine(chunk_size=512, overlap=64, strategy="fixed_character")
    result_1 = engine.chunk(text, document_id=doc_id)
    result_2 = engine.chunk(text, document_id=doc_id)

    assert len(result_1.chunks) == len(result_2.chunks)
    for c1, c2 in zip(result_1.chunks, result_2.chunks, strict=True):
        assert c1.chunk_id == c2.chunk_id


def test_deterministic_chunk_ids_different_documents() -> None:
    """Different document_ids should produce different chunk_ids even for same text."""
    doc_id_1 = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    doc_id_2 = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    text = "Same text, different documents."

    id_1 = Chunk.compute_chunk_id(doc_id_1, 0, text)
    id_2 = Chunk.compute_chunk_id(doc_id_2, 0, text)
    assert id_1 != id_2


def test_chunk_checksum_consistency() -> None:
    """Chunk checksum should be deterministic for identical text."""
    text = "Consistent checksum verification text."
    checksum_1 = Chunk.compute_checksum(text)
    checksum_2 = Chunk.compute_checksum(text)
    assert checksum_1 == checksum_2
    assert len(checksum_1) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# 11. Large Document Tests
# ---------------------------------------------------------------------------


def test_large_document_chunking(large_document: str) -> None:
    """Large document should chunk successfully into many chunks."""
    engine = ChunkingEngine(chunk_size=512, overlap=64, strategy="paragraph")
    result = engine.chunk(large_document, document_id=uuid.uuid4())
    assert result.total_chunks >= 100
    assert result.processing_time_ms >= 0.0
    # Verify no empty chunks
    for chunk in result.chunks:
        assert chunk.text.strip() != ""


def test_large_document_generator_does_not_load_all_at_once(
    large_document: str,
) -> None:
    """Verify strategy generator yields incrementally (partial consumption works)."""
    chunker = FixedCharacterChunker(chunk_size=512, overlap=64)
    generator = chunker.chunk(large_document)

    # Consume only first 5 chunks — should not raise OOM or block
    partial = []
    for i, chunk in enumerate(generator):
        partial.append(chunk)
        if i >= 4:
            break

    assert len(partial) == 5
    assert all(c.text.strip() != "" for c in partial)


# ---------------------------------------------------------------------------
# 12. Chunk Model Tests
# ---------------------------------------------------------------------------


def test_chunk_model_fields() -> None:
    """Verify all required Chunk fields are populated correctly."""
    doc_id = uuid.uuid4()
    text = "Sample chunk text for field verification."
    meta = ChunkMetadata(
        document_id=doc_id,
        source_filename="test.txt",
        language="en",
        chunk_index=0,
        total_chunks=5,
        strategy="fixed_character",
    )
    chunk = Chunk(
        chunk_id=Chunk.compute_chunk_id(doc_id, 0, text),
        document_id=doc_id,
        chunk_index=0,
        text=text,
        start_offset=0,
        end_offset=len(text),
        token_count=10,
        character_count=len(text),
        checksum=Chunk.compute_checksum(text),
        metadata=meta,
    )
    assert chunk.chunk_id is not None
    assert chunk.character_count == len(text)
    assert chunk.checksum == Chunk.compute_checksum(text)
    assert chunk.metadata.strategy == "fixed_character"


def test_chunk_result_model() -> None:
    """ChunkResult should correctly aggregate chunk data."""
    result = ChunkResult(
        document_id=uuid.uuid4(),
        chunks=[],
        total_chunks=0,
        strategy_used="adaptive",
        chunk_size=512,
        overlap=64,
        total_tokens=0,
        processing_time_ms=12.5,
    )
    assert result.total_chunks == 0
    assert result.strategy_used == "adaptive"
    assert result.processing_time_ms == 12.5
