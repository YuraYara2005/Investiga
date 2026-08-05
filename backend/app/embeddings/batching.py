"""Embedding Batch Processing Utilities.

Provides adaptive batch splitting for large input lists, respecting
model max_seq_length token limits and configurable batch size budgets.
"""

from __future__ import annotations

from collections.abc import Generator


def iter_batches(
    texts: list[str],
    batch_size: int,
) -> Generator[list[str], None, None]:
    """Yield successive fixed-size batches from a list of texts.

    Args:
        texts: Full list of text strings to embed.
        batch_size: Maximum number of texts per batch.

    Yields:
        list[str]: Batch of texts with length <= batch_size.
    """
    if batch_size <= 0:
        raise ValueError(f"batch_size must be > 0, got {batch_size}")

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        if batch:
            yield batch


def iter_batches_with_indices(
    texts: list[str],
    batch_size: int,
) -> Generator[tuple[int, list[str]], None, None]:
    """Yield (start_index, batch) tuples for tracking original positions.

    Args:
        texts: Full list of text strings to embed.
        batch_size: Maximum number of texts per batch.

    Yields:
        tuple[int, list[str]]: (start_index, batch) pairs.
    """
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        if batch:
            yield start, batch


def compute_adaptive_batch_size(
    text_lengths: list[int],
    target_batch_tokens: int = 32768,
    min_batch_size: int = 1,
    max_batch_size: int = 256,
) -> int:
    """Estimate an adaptive batch size based on average text length in tokens.

    Uses a simple heuristic: avg_token_estimate = avg_chars / 4.

    Args:
        text_lengths: Character lengths of the texts to embed.
        target_batch_tokens: Target total token budget per batch.
        min_batch_size: Minimum allowed batch size.
        max_batch_size: Maximum allowed batch size.

    Returns:
        int: Adaptive batch size clamped to [min_batch_size, max_batch_size].
    """
    if not text_lengths:
        return max_batch_size

    avg_chars = sum(text_lengths) / len(text_lengths)
    avg_tokens = max(1.0, avg_chars / 4.0)
    adaptive = int(target_batch_tokens / avg_tokens)
    return max(min_batch_size, min(max_batch_size, adaptive))


def validate_texts(texts: list[str]) -> list[str]:
    """Filter and validate a list of texts for embedding.

    Strips whitespace from each text. Returns the same list if all texts are
    non-empty after stripping.

    Args:
        texts: Raw list of texts to validate.

    Returns:
        list[str]: Stripped non-empty texts.

    Raises:
        EmptyEmbeddingInputException: If input is empty or all texts are blank.
    """
    from app.embeddings.exceptions import EmptyEmbeddingInputException

    if not texts:
        raise EmptyEmbeddingInputException()

    stripped = [t.strip() for t in texts]
    non_empty = [t for t in stripped if t]

    if not non_empty:
        raise EmptyEmbeddingInputException()

    return non_empty
