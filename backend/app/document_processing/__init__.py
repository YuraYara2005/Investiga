"""Intelligent Document Processing Subsystem for Investiga.

Provides robust multi-format text extraction (PDF, DOCX, Markdown, TXT),
Unicode NFKC normalization, control character sanitization, whitespace formatting,
and document metadata extraction.
"""

from app.document_processing.cleaners import TextCleaner
from app.document_processing.exceptions import (
    CorruptedDocumentException,
    DocumentProcessingException,
    EmptyDocumentException,
    UnsupportedDocumentException,
)
from app.document_processing.metadata import MetadataParser
from app.document_processing.models import (
    ExtractedDocument,
    ExtractedMetadata,
    ProcessingResult,
)
from app.document_processing.parser_factory import DocumentParserFactory
from app.document_processing.parsers import (
    BaseDocumentParser,
    DocxParser,
    HtmlParser,
    MarkdownParser,
    PdfParser,
    SourceCodeParser,
    TextParser,
)
from app.document_processing.processor import DocumentProcessor

__all__ = [
    "BaseDocumentParser",
    "CorruptedDocumentException",
    "DocumentParserFactory",
    "DocumentProcessingException",
    "DocumentProcessor",
    "DocxParser",
    "EmptyDocumentException",
    "ExtractedDocument",
    "ExtractedMetadata",
    "HtmlParser",
    "MarkdownParser",
    "MetadataParser",
    "PdfParser",
    "ProcessingResult",
    "SourceCodeParser",
    "TextCleaner",
    "TextParser",
    "UnsupportedDocumentException",
]
