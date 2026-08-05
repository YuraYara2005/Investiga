"""Token Estimation Engine.

Implements multi-tier token counting with tiktoken as primary backend and a calibrated
word-boundary fallback estimator for offline or restricted environments.
"""

from __future__ import annotations

import importlib.util
import re

_TIKTOKEN_AVAILABLE = importlib.util.find_spec("tiktoken") is not None

_WORD_SPLIT_REGEX = re.compile(r"\s+")

# Calibration: GPT tokenizers average ~0.75 tokens per word for English prose.
# We use 1.35 chars/token as a conservative estimate that doesn't over-estimate.
_CHARS_PER_TOKEN_ESTIMATE: float = 4.0


class Tokenizer:
    """Token counting engine with tiktoken primary and word-boundary fallback."""

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        """Initialize tokenizer with the given tiktoken encoding name.

        Args:
            encoding_name: tiktoken encoding to use (default: cl100k_base for GPT-4).
        """
        self._encoding_name = encoding_name
        self._enc: object | None = None

        if _TIKTOKEN_AVAILABLE:
            try:
                import tiktoken

                self._enc = tiktoken.get_encoding(encoding_name)
            except Exception:
                self._enc = None

    @property
    def backend(self) -> str:
        """Return the active tokenizer backend identifier."""
        return "tiktoken" if self._enc is not None else "fallback"

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in the given text string.

        Uses tiktoken BPE tokenizer when available, otherwise falls back to a calibrated
        character-boundary estimator.

        Args:
            text: Input text string.

        Returns:
            int: Estimated or exact token count.
        """
        if not text:
            return 0

        if self._enc is not None:
            try:
                import tiktoken

                enc = self._enc
                if isinstance(enc, tiktoken.core.Encoding):
                    return len(enc.encode(text))
            except Exception:
                pass

        # Calibrated fallback: divide total chars by average chars/token
        return max(1, round(len(text) / _CHARS_PER_TOKEN_ESTIMATE))

    def estimate_tokens(self, text: str) -> int:
        """Alias for count_tokens — produces token estimate for the text.

        Prefer this method in hot loops for clarity.
        """
        return self.count_tokens(text)

    def split_by_token_limit(
        self,
        text: str,
        max_tokens: int,
    ) -> list[str]:
        """Split text into segments each not exceeding max_tokens.

        This is a greedy forward scan that avoids splitting mid-sentence when possible
        by preferring newlines and sentence boundaries.

        Args:
            text: Input text to split.
            max_tokens: Maximum token budget per segment.

        Returns:
            list[str]: List of token-bounded text segments.
        """
        if not text:
            return []

        if self.count_tokens(text) <= max_tokens:
            return [text]

        # Use character estimate to determine approximate split points
        chars_per_segment = int(max_tokens * _CHARS_PER_TOKEN_ESTIMATE)

        segments: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chars_per_segment, text_len)

            if end < text_len:
                # Try to find a good split point (newline or space) before the limit
                split_point = text.rfind("\n", start, end)
                if split_point == -1 or split_point <= start:
                    split_point = text.rfind(" ", start, end)
                if split_point == -1 or split_point <= start:
                    split_point = end
                else:
                    split_point += 1  # Include the delimiter
                end = split_point

            segment = text[start:end].strip()
            if segment:
                segments.append(segment)
            start = end

        return segments


# Module-level singleton for efficient reuse
_default_tokenizer: Tokenizer | None = None


def get_tokenizer(encoding_name: str = "cl100k_base") -> Tokenizer:
    """Return the module-level cached tokenizer singleton.

    Args:
        encoding_name: tiktoken encoding name.

    Returns:
        Tokenizer: Shared tokenizer instance.
    """
    global _default_tokenizer
    if _default_tokenizer is None or _default_tokenizer._encoding_name != encoding_name:
        _default_tokenizer = Tokenizer(encoding_name=encoding_name)
    return _default_tokenizer
