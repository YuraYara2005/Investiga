"""Text Cleaning, Sanitization, and Normalization Utilities.

Implements high-performance text sanitization:
- NFKC Unicode normalization
- Control character and null byte stripping
- Invisible character and zero-width marker removal
- Deterministic line ending unification
- Paragraph-preserving whitespace collapsing
- Text statistical analysis (word & character counting)
"""

import re
import unicodedata

# Pre-compiled regex patterns for maximum execution throughput
_NULL_BYTES_REGEX = re.compile(r"[\x00]")
_INVISIBLE_CHARS_REGEX = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad\u2060]"
)
# Disallow non-printable control characters except standard whitespace \t and \n
_CONTROL_CHARS_REGEX = re.compile(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
# Unify line endings
_LINE_ENDINGS_REGEX = re.compile(r"\r\n|\r")
# Collapse horizontal whitespace (spaces, tabs) except newline
_HORIZONTAL_SPACES_REGEX = re.compile(r"[^\S\n]+")
# Collapse excessive consecutive newlines (more than 2) to maintain clean paragraphs
_EXCESSIVE_NEWLINES_REGEX = re.compile(r"\n{3,}")
# Split words for token counting
_WORD_BOUNDARY_REGEX = re.compile(r"\s+")


class TextCleaner:
    """Enterprise text sanitization and normalization pipeline."""

    @staticmethod
    def normalize_unicode(text: str) -> str:
        """Normalize Unicode characters into canonical compatibility decomposition (NFKC).

        Ensures full character compatibility across ligatures, fullwidth glyphs, and accent combinations.
        """
        if not text:
            return ""
        return unicodedata.normalize("NFKC", text)

    @staticmethod
    def remove_control_characters(text: str) -> str:
        """Remove null bytes, zero-width markers, and non-printable control characters.

        Preserves valid whitespace characters (space, tab, newline).
        """
        if not text:
            return ""
        # 1. Strip null bytes
        cleaned = _NULL_BYTES_REGEX.sub("", text)
        # 2. Strip invisible zero-width characters and soft hyphens
        cleaned = _INVISIBLE_CHARS_REGEX.sub("", cleaned)
        # 3. Strip remaining non-printable control chars
        cleaned = _CONTROL_CHARS_REGEX.sub("", cleaned)
        return cleaned

    @staticmethod
    def normalize_line_endings(text: str) -> str:
        """Unify CRLF and CR carriage returns into standard Unix newline (LF: `\\n`)."""
        if not text:
            return ""
        return _LINE_ENDINGS_REGEX.sub("\n", text)

    @staticmethod
    def collapse_whitespace(text: str) -> str:
        """Collapse redundant horizontal spaces while preserving structural paragraph breaks.

        Collapses continuous spaces/tabs into a single space, strips trailing line whitespace,
        and limits consecutive newlines to at most two (paragraph separation).
        """
        if not text:
            return ""

        # Normalize horizontal spaces per line
        lines: list[str] = []
        for line in text.split("\n"):
            # Collapse multiple spaces and strip ends of each line
            collapsed_line = _HORIZONTAL_SPACES_REGEX.sub(" ", line).strip()
            lines.append(collapsed_line)

        joined = "\n".join(lines)
        # Collapse 3+ newlines into 2 newlines
        return _EXCESSIVE_NEWLINES_REGEX.sub("\n\n", joined).strip()

    @classmethod
    def clean(cls, text: str) -> str:
        """Execute the full end-to-end text sanitization and normalization pipeline.

        Execution Order:
        1. Line ending normalization
        2. Unicode NFKC normalization
        3. Control character & invisible marker stripping
        4. Paragraph-preserving whitespace collapsing
        5. Leading/trailing trimming

        Args:
            text: Unfiltered raw extracted text string.

        Returns:
            str: Clean, standardized, high-fidelity text string.
        """
        if not text:
            return ""

        # 1. Normalize line breaks first
        step1 = cls.normalize_line_endings(text)

        # 2. Unicode normalization
        step2 = cls.normalize_unicode(step1)

        # 3. Strip control characters and invisible tokens
        step3 = cls.remove_control_characters(step2)

        # 4. Whitespace collapsing and paragraph preservation
        step4 = cls.collapse_whitespace(step3)

        return step4

    @staticmethod
    def count_words(text: str) -> int:
        """Calculate total word count for cleaned text."""
        stripped = text.strip()
        if not stripped:
            return 0
        return len(_WORD_BOUNDARY_REGEX.split(stripped))

    @staticmethod
    def count_characters(text: str) -> int:
        """Calculate total character count excluding trailing outer whitespace."""
        return len(text)
