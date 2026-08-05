"""PDF Document Parser using PyMuPDF (fitz).

Implements memory-efficient, streaming page-by-page text extraction and metadata retrieval
for Portable Document Format (.pdf) files.
"""

from collections.abc import Generator
from pathlib import Path
from typing import ClassVar

import fitz  # PyMuPDF

from app.document_processing.exceptions import CorruptedDocumentException
from app.document_processing.metadata import MetadataParser
from app.document_processing.models import ExtractedDocument, ExtractedMetadata
from app.document_processing.parsers.base_parser import BaseDocumentParser


class PdfParser(BaseDocumentParser):
    """High-performance parser for PDF documents utilizing PyMuPDF engine."""

    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = {".pdf"}
    SUPPORTED_MIME_TYPES: ClassVar[set[str]] = {"application/pdf", "application/x-pdf"}

    def supports(self, extension: str, mime_type: str | None = None) -> bool:
        """Check if parser supports PDF format."""
        norm_ext = (
            extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        )
        if norm_ext in self.SUPPORTED_EXTENSIONS:
            return True
        if mime_type and mime_type.lower() in self.SUPPORTED_MIME_TYPES:
            return True
        return False

    def _open_pdf(self, content: bytes | Path) -> fitz.Document:
        """Safely open PyMuPDF document handle from bytes or filepath."""
        try:
            if isinstance(content, (str, Path)):
                return fitz.open(str(content))
            return fitz.open(stream=content, filetype="pdf")
        except Exception as exc:
            filename = (
                str(content) if isinstance(content, (str, Path)) else "in-memory.pdf"
            )
            raise CorruptedDocumentException(
                filename=filename,
                reason=f"Failed to open PDF document: {exc}",
            ) from exc

    def _iter_pages_text(self, doc: fitz.Document) -> Generator[str, None, None]:
        """Yield extracted text page-by-page to prevent excessive peak memory allocation."""
        for page_index in range(doc.page_count):
            try:
                page = doc.load_page(page_index)
                page_text = page.get_text("text")
                if page_text:
                    yield page_text
            except Exception:
                continue

    def extract_text(self, content: bytes | Path) -> str:
        """Extract all text pages from PDF."""
        doc = self._open_pdf(content)
        try:
            if doc.is_encrypted:
                try:
                    # Attempt empty password authentication for read-protected files
                    doc.authenticate("")
                except Exception as exc:
                    raise CorruptedDocumentException(
                        filename="encrypted.pdf",
                        reason=f"PDF is encrypted with password protection: {exc}",
                    ) from exc

            pages = list(self._iter_pages_text(doc))
            return "\n\n".join(pages)
        finally:
            doc.close()

    def extract_metadata(self, content: bytes | Path) -> ExtractedMetadata:
        """Extract metadata properties from PDF headers."""
        doc = self._open_pdf(content)
        try:
            raw_meta = doc.metadata or {}
            page_count = max(1, doc.page_count)

            title = raw_meta.get("title") or None
            author = raw_meta.get("author") or None
            creation_date = MetadataParser.parse_pdf_date(raw_meta.get("creationDate"))
            modification_date = MetadataParser.parse_pdf_date(raw_meta.get("modDate"))

            # Filter empty strings
            resolved_title = title.strip() if title and title.strip() else None
            resolved_author = author.strip() if author and author.strip() else None

            return ExtractedMetadata(
                title=resolved_title,
                author=resolved_author,
                creation_date=creation_date,
                modification_date=modification_date,
                page_count=page_count,
                extra_metadata={
                    "format": raw_meta.get("format"),
                    "producer": raw_meta.get("producer"),
                    "creator": raw_meta.get("creator"),
                    "subject": raw_meta.get("subject"),
                    "keywords": raw_meta.get("keywords"),
                },
            )
        finally:
            doc.close()

    def parse(self, content: bytes | Path) -> ExtractedDocument:
        """Efficient combined single-pass parse of text and metadata."""
        doc = self._open_pdf(content)
        try:
            if doc.is_encrypted:
                try:
                    doc.authenticate("")
                except Exception as exc:
                    raise CorruptedDocumentException(
                        filename="encrypted.pdf",
                        reason=f"PDF is encrypted with password protection: {exc}",
                    ) from exc

            # 1. Text extraction
            pages = list(self._iter_pages_text(doc))
            raw_text = "\n\n".join(pages)

            # 2. Metadata extraction
            raw_meta = doc.metadata or {}
            page_count = max(1, doc.page_count)

            title = raw_meta.get("title") or None
            author = raw_meta.get("author") or None
            creation_date = MetadataParser.parse_pdf_date(raw_meta.get("creationDate"))
            modification_date = MetadataParser.parse_pdf_date(raw_meta.get("modDate"))

            resolved_title = title.strip() if title and title.strip() else None
            resolved_author = author.strip() if author and author.strip() else None

            metadata = ExtractedMetadata(
                title=resolved_title,
                author=resolved_author,
                creation_date=creation_date,
                modification_date=modification_date,
                page_count=page_count,
                extra_metadata={
                    "format": raw_meta.get("format"),
                    "producer": raw_meta.get("producer"),
                    "creator": raw_meta.get("creator"),
                    "subject": raw_meta.get("subject"),
                },
            )

            return ExtractedDocument(raw_text=raw_text, metadata=metadata)
        finally:
            doc.close()
