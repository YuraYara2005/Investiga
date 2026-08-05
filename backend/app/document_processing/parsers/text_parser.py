"""Plaintext and Structured Configuration Document Parser.

Implements robust encoding-tolerant text extraction for plain text files (.txt, .log, .csv, .json, .yaml).
"""

from pathlib import Path
from typing import ClassVar

from app.document_processing.models import ExtractedDocument, ExtractedMetadata
from app.document_processing.parsers.base_parser import BaseDocumentParser


class TextParser(BaseDocumentParser):
    """Parser for raw plaintext, logs, and structured text configurations."""

    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = {
        ".txt",
        ".text",
        ".log",
        ".csv",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".ini",
        ".conf",
        ".env",
    }
    SUPPORTED_MIME_TYPES: ClassVar[set[str]] = {
        "text/plain",
        "text/csv",
        "text/tab-separated-values",
        "application/json",
        "application/x-yaml",
        "text/yaml",
        "text/x-yaml",
        "application/xml",
        "text/xml",
    }

    def supports(self, extension: str, mime_type: str | None = None) -> bool:
        """Check if parser supports plaintext format."""
        norm_ext = (
            extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        )
        if norm_ext in self.SUPPORTED_EXTENSIONS:
            return True
        if mime_type and mime_type.lower() in self.SUPPORTED_MIME_TYPES:
            return True
        return False

    def _read_text(self, content: bytes | Path) -> str:
        """Decode byte payload into string with multi-encoding fallback."""
        if isinstance(content, (str, Path)):
            raw_bytes = Path(content).read_bytes()
        else:
            raw_bytes = content

        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return raw_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                return raw_bytes.decode("latin-1", errors="replace")

    def extract_text(self, content: bytes | Path) -> str:
        """Extract raw plaintext from file."""
        return self._read_text(content)

    def extract_metadata(self, content: bytes | Path) -> ExtractedMetadata:
        """Construct baseline metadata container for plaintext."""
        return ExtractedMetadata(
            page_count=1,
        )

    def parse(self, content: bytes | Path) -> ExtractedDocument:
        """Execute single-pass text and metadata extraction."""
        text = self._read_text(content)
        metadata = ExtractedMetadata(
            page_count=1,
        )
        return ExtractedDocument(raw_text=text, metadata=metadata)
