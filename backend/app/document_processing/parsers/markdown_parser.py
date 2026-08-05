"""Markdown Document Parser.

Implements text extraction, YAML frontmatter property parsing, heading-based title
inference, and clean text representation for Markdown (.md) documents.
"""

import re
from pathlib import Path
from typing import ClassVar

from app.document_processing.metadata import MetadataParser
from app.document_processing.models import ExtractedDocument, ExtractedMetadata
from app.document_processing.parsers.base_parser import BaseDocumentParser

_H1_HEADER_REGEX = re.compile(r"^#\s+(.+)$", re.MULTILINE)


class MarkdownParser(BaseDocumentParser):
    """Parser for Markdown (.md, .markdown) formatted documents."""

    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = {".md", ".markdown", ".mdown", ".mkd"}
    SUPPORTED_MIME_TYPES: ClassVar[set[str]] = {"text/markdown", "text/x-markdown"}

    def supports(self, extension: str, mime_type: str | None = None) -> bool:
        """Check if parser supports Markdown format."""
        norm_ext = (
            extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        )
        if norm_ext in self.SUPPORTED_EXTENSIONS:
            return True
        if mime_type and mime_type.lower() in self.SUPPORTED_MIME_TYPES:
            return True
        return False

    def _read_text(self, content: bytes | Path) -> str:
        """Decode content bytes or read file from disk."""
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
        """Extract plain text from markdown, stripping frontmatter."""
        full_text = self._read_text(content)
        _, body = MetadataParser.extract_frontmatter(full_text)
        return body

    def extract_metadata(self, content: bytes | Path) -> ExtractedMetadata:
        """Extract metadata from YAML frontmatter and top-level markdown headers."""
        full_text = self._read_text(content)
        frontmatter, body = MetadataParser.extract_frontmatter(full_text)

        title = frontmatter.get("title")
        if not title:
            h1_match = _H1_HEADER_REGEX.search(body)
            if h1_match:
                title = h1_match.group(1).strip()

        author = frontmatter.get("author")
        creation_date = MetadataParser.parse_iso_date(
            frontmatter.get("date") or frontmatter.get("created")
        )
        modification_date = MetadataParser.parse_iso_date(
            frontmatter.get("updated") or frontmatter.get("modified")
        )

        return ExtractedMetadata(
            title=title,
            author=author,
            creation_date=creation_date,
            modification_date=modification_date,
            page_count=1,
            language=frontmatter.get("lang") or frontmatter.get("language"),
            extra_metadata={
                k: v
                for k, v in frontmatter.items()
                if k
                not in [
                    "title",
                    "author",
                    "date",
                    "created",
                    "updated",
                    "modified",
                    "lang",
                    "language",
                ]
            },
        )

    def parse(self, content: bytes | Path) -> ExtractedDocument:
        """Single-pass parse of markdown document."""
        full_text = self._read_text(content)
        frontmatter, body = MetadataParser.extract_frontmatter(full_text)

        title = frontmatter.get("title")
        if not title:
            h1_match = _H1_HEADER_REGEX.search(body)
            if h1_match:
                title = h1_match.group(1).strip()

        author = frontmatter.get("author")
        creation_date = MetadataParser.parse_iso_date(
            frontmatter.get("date") or frontmatter.get("created")
        )
        modification_date = MetadataParser.parse_iso_date(
            frontmatter.get("updated") or frontmatter.get("modified")
        )

        metadata = ExtractedMetadata(
            title=title,
            author=author,
            creation_date=creation_date,
            modification_date=modification_date,
            page_count=1,
            language=frontmatter.get("lang") or frontmatter.get("language"),
            extra_metadata={
                k: v
                for k, v in frontmatter.items()
                if k
                not in [
                    "title",
                    "author",
                    "date",
                    "created",
                    "updated",
                    "modified",
                    "lang",
                    "language",
                ]
            },
        )

        return ExtractedDocument(raw_text=body, metadata=metadata)
