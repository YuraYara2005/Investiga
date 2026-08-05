"""Document Parser Factory.

Provides centralized parser discovery, registry management, and dynamic parser selection
based on document extension and MIME type.
"""

from pathlib import PurePath

from app.document_processing.exceptions import UnsupportedDocumentException
from app.document_processing.parsers.base_parser import BaseDocumentParser
from app.document_processing.parsers.docx_parser import DocxParser
from app.document_processing.parsers.markdown_parser import MarkdownParser
from app.document_processing.parsers.pdf_parser import PdfParser
from app.document_processing.parsers.text_parser import TextParser


class DocumentParserFactory:
    """Factory for selecting and instantiating format-specific document parsers."""

    def __init__(self, parsers: list[BaseDocumentParser] | None = None) -> None:
        """Initialize parser registry with standard default parsers or custom overrides."""
        if parsers is not None:
            self._parsers: list[BaseDocumentParser] = list(parsers)
        else:
            self._parsers = [
                PdfParser(),
                DocxParser(),
                MarkdownParser(),
                TextParser(),
            ]

    def register_parser(
        self, parser: BaseDocumentParser, prepend: bool = False
    ) -> None:
        """Register a new custom parser into the factory registry.

        Args:
            parser: Concrete instance of BaseDocumentParser.
            prepend: If True, prioritizes this parser before default parsers.
        """
        if prepend:
            self._parsers.insert(0, parser)
        else:
            self._parsers.append(parser)

    def get_parser(
        self,
        filename_or_extension: str,
        mime_type: str | None = None,
    ) -> BaseDocumentParser:
        """Resolve the appropriate parser for a given filename/extension and MIME type.

        Args:
            filename_or_extension: File path, filename, or file extension (e.g. 'doc.pdf' or '.pdf').
            mime_type: Optional MIME content type.

        Returns:
            BaseDocumentParser: Matching concrete parser instance.

        Raises:
            UnsupportedDocumentException: If no registered parser supports the file format.
        """
        extension = PurePath(filename_or_extension).suffix
        if not extension and filename_or_extension.startswith("."):
            extension = filename_or_extension
        elif not extension and not filename_or_extension.startswith("."):
            extension = f".{filename_or_extension}"

        norm_ext = extension.lower()

        for parser in self._parsers:
            if parser.supports(norm_ext, mime_type):
                return parser

        raise UnsupportedDocumentException(
            extension=norm_ext,
            mime_type=mime_type,
            details={"input": filename_or_extension},
        )
