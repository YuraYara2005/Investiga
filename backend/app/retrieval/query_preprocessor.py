"""Query Preprocessing and Validation Engine for Retrieval.

Provides Unicode normalization (NFKC), control character removal, whitespace
standardization, query length validation, and linguistic term tokenization for
sparse BM25 search.
"""

from __future__ import annotations

import re
import unicodedata

from app.retrieval.exceptions import InvalidQueryException

# Standard lightweight English stopword set to optimize BM25 term weighting
DEFAULT_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren't",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can't",
        "cannot",
        "could",
        "couldn't",
        "did",
        "didn't",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "hadn't",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "he'd",
        "he'll",
        "he's",
        "her",
        "here",
        "here's",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "how's",
        "i",
        "i'd",
        "i'll",
        "i'm",
        "i've",
        "if",
        "in",
        "into",
        "is",
        "isn't",
        "it",
        "it's",
        "its",
        "itself",
        "let's",
        "me",
        "more",
        "most",
        "mustn't",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shan't",
        "she",
        "she'd",
        "she'll",
        "she's",
        "should",
        "shouldn't",
        "so",
        "some",
        "such",
        "than",
        "that",
        "that's",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "there's",
        "these",
        "they",
        "they'd",
        "they'll",
        "they're",
        "they've",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn't",
        "we",
        "we'd",
        "we'll",
        "we're",
        "we've",
        "were",
        "weren't",
        "what",
        "what's",
        "when",
        "when's",
        "where",
        "where's",
        "which",
        "while",
        "who",
        "who's",
        "whom",
        "why",
        "why's",
        "with",
        "won't",
        "would",
        "wouldn't",
        "you",
        "you'd",
        "you'll",
        "you're",
        "you've",
        "your",
        "yours",
        "yourself",
        "yourselves",
    }
)

# Token pattern matching alphanumeric tokens with hyphens/underscores (e.g. error codes, identifiers)
TOKEN_REGEX = re.compile(r"[a-zA-Z0-9_\-]+")
CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


class QueryPreprocessor:
    """Enterprise query sanitization, normalization, and tokenization engine."""

    def __init__(
        self,
        max_query_length: int = 4096,
        remove_stopwords: bool = True,
        stopwords: frozenset[str] | None = None,
    ) -> None:
        """Initialize QueryPreprocessor.

        Args:
            max_query_length: Maximum permitted character length of query.
            remove_stopwords: Whether to filter out stopwords for sparse token generation.
            stopwords: Custom stopword collection or default if None.
        """
        self._max_query_length = max_query_length
        self._remove_stopwords = remove_stopwords
        self._stopwords = stopwords if stopwords is not None else DEFAULT_STOPWORDS

    def normalize(self, query: str) -> str:
        """Normalize raw query string.

        Performs:
        1. Non-empty validation
        2. Unicode normalization (NFKC)
        3. Control character removal
        4. Whitespace collapsing and trimming
        5. Length limit enforcement

        Args:
            query: Raw user search string.

        Returns:
            str: Normalized clean query text.

        Raises:
            InvalidQueryException: If query is blank or exceeds maximum length.
        """
        if query is None:
            raise InvalidQueryException(
                reason="Query string cannot be None.",
                query_text="",
            )

        # 1. Unicode NFKC normalization
        normalized = unicodedata.normalize("NFKC", str(query))

        # 2. Remove non-printable control characters
        normalized = CONTROL_CHARS_REGEX.sub(" ", normalized)

        # 3. Collapse multiple whitespace chars and strip edges
        normalized = " ".join(normalized.split())

        if not normalized:
            raise InvalidQueryException(
                reason="Query text cannot be empty or solely whitespace.",
                query_text=query,
            )

        if len(normalized) > self._max_query_length:
            raise InvalidQueryException(
                reason=f"Query length ({len(normalized)} chars) exceeds limit of {self._max_query_length} characters.",
                query_text=normalized,
                details={
                    "length": len(normalized),
                    "max_length": self._max_query_length,
                },
            )

        return normalized

    def tokenize_for_sparse(self, normalized_query: str) -> list[str]:
        """Extract linguistic search tokens from normalized query for BM25 scoring.

        Args:
            normalized_query: Normalized query string.

        Returns:
            list[str]: Lowercased, cleaned search tokens.
        """
        raw_tokens = TOKEN_REGEX.findall(normalized_query.lower())
        tokens: list[str] = []
        for tok in raw_tokens:
            cleaned = tok.strip("-_")
            if len(cleaned) <= 1 and not cleaned.isalnum():
                continue
            if self._remove_stopwords and cleaned in self._stopwords:
                continue
            if cleaned:
                tokens.append(cleaned)

        # If all tokens were stopwords (e.g. "what is that"), fall back to raw tokens to prevent zero-match
        if not tokens and raw_tokens:
            tokens = [t.strip("-_") for t in raw_tokens if t.strip("-_")]

        return tokens

    def preprocess(self, query: str) -> tuple[str, list[str]]:
        """Execute full preprocessing pipeline returning normalized text and BM25 tokens.

        Args:
            query: Raw input query string.

        Returns:
            tuple[str, list[str]]: (normalized_query, token_list)
        """
        normalized = self.normalize(query)
        tokens = self.tokenize_for_sparse(normalized)
        return normalized, tokens
