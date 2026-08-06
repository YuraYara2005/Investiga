"""HTML Document Parser for Technical Websites and Web Documentation.

Uses BeautifulSoup4 to extract high-fidelity structured text from HTML/HTM documents,
stripping non-content boilerplate (scripts, styles, navigation, headers, footers, asides,
and advertisements) while preserving structural semantics (headings, paragraphs, tables,
ordered/unordered lists, preformatted code blocks, blockquotes, and metadata).
"""

from __future__ import annotations

import re
from pathlib import Path, PurePath
from typing import Any, ClassVar

from bs4 import BeautifulSoup, Comment, NavigableString, PageElement, Tag

from app.core.logging import get_logger
from app.document_processing.metadata import MetadataParser
from app.document_processing.models import ExtractedDocument, ExtractedMetadata
from app.document_processing.parsers.base_parser import BaseDocumentParser

logger = get_logger(__name__)

# Tags to completely strip from DOM along with all their children
_STRIP_TAGS: frozenset[str] = frozenset(
    {
        "script",
        "style",
        "nav",
        "footer",
        "header",
        "aside",
        "noscript",
        "svg",
        "canvas",
        "iframe",
        "frame",
        "frameset",
        "embed",
        "object",
        "applet",
    }
)

# Regex pattern to identify advertisement classes, IDs, and roles
_AD_IDENTIFIER_REGEX = re.compile(
    r"(?i)(^|[-_ ])(ad|ads|advert|advertisement|banner|sponsor|sponsored|"
    r"google-ad|ad-box|ad-container|ad-slot|ad-wrapper|adsbygoogle)([-_ ]|$)"
)


class HtmlParser(BaseDocumentParser):
    """Parser for HTML and XHTML web documents (.html, .htm)."""

    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = {".html", ".htm"}
    SUPPORTED_MIME_TYPES: ClassVar[set[str]] = {
        "text/html",
        "application/xhtml+xml",
    }

    def supports(self, extension: str, mime_type: str | None = None) -> bool:
        """Evaluate whether this parser supports the given extension or MIME type."""
        ext_clean = extension.lower().strip()
        if ext_clean in self.SUPPORTED_EXTENSIONS:
            return True

        suffix = PurePath(ext_clean).suffix
        if suffix in self.SUPPORTED_EXTENSIONS:
            return True

        norm_ext = ext_clean if ext_clean.startswith(".") else f".{ext_clean}"
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

        if not raw_bytes:
            return ""

        # Try standard encodings with fallback
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return raw_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                try:
                    return raw_bytes.decode("windows-1252")
                except UnicodeDecodeError:
                    return raw_bytes.decode("latin-1", errors="replace")

    def _create_soup(self, html_text: str) -> BeautifulSoup:
        """Parse HTML string with BeautifulSoup html.parser."""
        return BeautifulSoup(html_text, "html.parser")

    def _clean_soup(self, soup: BeautifulSoup) -> None:
        """Remove unwanted tags, comments, and advertisements in-place."""
        # 1. Remove HTML comments
        for comment in list(soup.find_all(string=lambda text: isinstance(text, Comment))):
            comment.extract()

        # 2. Remove non-content structural tags
        for tag_name in _STRIP_TAGS:
            for tag in list(soup.find_all(tag_name)):
                if getattr(tag, "attrs", None) is not None:
                    tag.decompose()

        # 3. Remove advertisement elements by class, id, or role
        for tag in list(soup.find_all(True)):
            if not isinstance(tag, Tag) or getattr(tag, "attrs", None) is None:
                continue
            # Check class
            classes_val = tag.get("class")
            classes = classes_val if isinstance(classes_val, list) else ([classes_val] if classes_val else [])
            class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
            tag_id = str(tag.get("id", ""))
            tag_role = str(tag.get("role", ""))

            if (
                _AD_IDENTIFIER_REGEX.search(class_str)
                or _AD_IDENTIFIER_REGEX.search(tag_id)
                or _AD_IDENTIFIER_REGEX.search(tag_role)
                or (tag.name == "ins" and "adsbygoogle" in class_str)
            ):
                tag.decompose()

    def _format_table(self, table: Tag) -> str:
        """Format an HTML table into a clean Markdown-compatible table."""
        rows_data: list[list[str]] = []
        for tr in table.find_all("tr", recursive=True):
            cells = tr.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            row = [
                " ".join(c.get_text(separator=" ", strip=True).split()) for c in cells
            ]
            rows_data.append(row)

        if not rows_data:
            return ""

        col_count = max(len(r) for r in rows_data)
        if col_count == 0:
            return ""

        # Normalize rectangular matrix
        matrix: list[list[str]] = []
        for r in rows_data:
            padded = r + [""] * (col_count - len(r))
            matrix.append(padded)

        lines: list[str] = []
        # Header row
        header = matrix[0]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * col_count) + " |")

        # Data rows
        for row in matrix[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n\n" + "\n".join(lines) + "\n\n"

    def _format_list(self, list_tag: Tag, ordered: bool = False) -> str:
        """Format HTML list (ul / ol) into Markdown list text."""
        items: list[str] = []
        index = 1
        for li in list_tag.find_all("li", recursive=False):
            li_text = " ".join(li.get_text(separator=" ", strip=True).split())
            if not li_text:
                continue
            prefix = f"{index}." if ordered else "-"
            items.append(f"{prefix} {li_text}")
            if ordered:
                index += 1
        return "\n".join(items)

    def _extract_element_text(self, element: PageElement) -> str:
        """Recursively process DOM nodes into structured Markdown-like representation."""
        if isinstance(element, NavigableString):
            return str(element)

        if not isinstance(element, Tag):
            return ""

        tag_name = element.name.lower()

        # Headings (H1 - H6)
        if tag_name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag_name[1])
            heading_text = " ".join(
                element.get_text(separator=" ", strip=True).split()
            )
            if heading_text:
                prefix = "#" * level
                return f"\n\n{prefix} {heading_text}\n\n"
            return ""

        # Preformatted code blocks
        if tag_name == "pre":
            code_tag = element.find("code")
            if code_tag and isinstance(code_tag, Tag):
                code_text = code_tag.get_text()
                # Check for language class (e.g., class="language-python")
                classes_val = code_tag.get("class")
                classes = classes_val if isinstance(classes_val, list) else ([classes_val] if classes_val else [])
                class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
                lang_match = re.search(r"language-(\w+)", class_str)
                lang = lang_match.group(1) if lang_match else ""
                return f"\n\n```{lang}\n{code_text}\n```\n\n"
            code_text = element.get_text()
            return f"\n\n```\n{code_text}\n```\n\n"

        # Inline code
        if tag_name == "code":
            code_text = element.get_text()
            if "\n" in code_text:
                return f"\n\n```\n{code_text}\n```\n\n"
            return f"`{code_text}`"

        # Tables
        if tag_name == "table":
            return self._format_table(element)

        # Unordered Lists
        if tag_name == "ul":
            return "\n\n" + self._format_list(element, ordered=False) + "\n\n"

        # Ordered Lists
        if tag_name == "ol":
            return "\n\n" + self._format_list(element, ordered=True) + "\n\n"

        # Blockquotes
        if tag_name == "blockquote":
            inner_text = " ".join(
                element.get_text(separator=" ", strip=True).split()
            )
            if inner_text:
                return f"\n\n> {inner_text}\n\n"
            return ""

        # Paragraphs & Division blocks
        if tag_name == "p":
            inner_pieces: list[str] = []
            for child in element.children:
                inner_pieces.append(self._extract_element_text(child))
            paragraph_text = "".join(inner_pieces).strip()
            if paragraph_text:
                return f"\n\n{paragraph_text}\n\n"
            return ""

        if tag_name == "br":
            return "\n"

        if tag_name == "hr":
            return "\n\n---\n\n"

        # General recursive container
        pieces: list[str] = []
        for child in element.children:
            pieces.append(self._extract_element_text(child))
        return "".join(pieces)

    def extract_text(self, content: bytes | Path) -> str:
        """Extract clean structured text from HTML payload."""
        html_text = self._read_text(content)
        if not html_text.strip():
            return ""

        soup = self._create_soup(html_text)
        self._clean_soup(soup)

        # Prefer main / article / body if present to focus on primary content
        root = soup.find(["main", "article"]) or soup.body or soup

        raw_extracted = self._extract_element_text(root)

        # Unify multiple newlines
        cleaned = re.sub(r"\n{3,}", "\n\n", raw_extracted).strip()
        return cleaned

    def extract_metadata(self, content: bytes | Path) -> ExtractedMetadata:
        """Extract metadata (title, language, description, author, dates) from HTML."""
        html_text = self._read_text(content)
        if not html_text.strip():
            return ExtractedMetadata(page_count=1)

        soup = self._create_soup(html_text)

        # 1. Title
        title: str | None = None
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.string.strip()

        if not title:
            og_title = soup.find("meta", property="og:title") or soup.find(
                "meta", attrs={"name": "twitter:title"}
            )
            if og_title and og_title.get("content"):
                title = str(og_title["content"]).strip()

        if not title:
            h1_tag = soup.find("h1")
            if h1_tag:
                title = h1_tag.get_text(strip=True)

        # 2. Language
        language: str | None = None
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            language = str(html_tag["lang"]).strip().split("-")[0].lower()

        if not language:
            http_lang = soup.find(
                "meta", attrs={"http-equiv": re.compile(r"content-language", re.I)}
            )
            if http_lang and http_lang.get("content"):
                language = str(http_lang["content"]).strip().split("-")[0].lower()

        # 3. Description
        description: str | None = None
        desc_meta = soup.find(
            "meta", attrs={"name": re.compile(r"^description$", re.I)}
        ) or soup.find("meta", property="og:description")
        if desc_meta and desc_meta.get("content"):
            description = str(desc_meta["content"]).strip()

        # 4. Author
        author: str | None = None
        author_meta = soup.find(
            "meta", attrs={"name": re.compile(r"^author$", re.I)}
        ) or soup.find("meta", property="article:author")
        if author_meta and author_meta.get("content"):
            author = str(author_meta["content"]).strip()

        # 5. Creation and modification dates
        creation_date = None
        mod_date = None
        date_meta = soup.find(
            "meta",
            attrs={"name": re.compile(r"^(date|created|publication_date)$", re.I)},
        ) or soup.find("meta", property="article:published_time")
        if date_meta and date_meta.get("content"):
            creation_date = MetadataParser.parse_iso_date(str(date_meta["content"]))

        updated_meta = soup.find(
            "meta",
            attrs={"name": re.compile(r"^(updated|modified|last-modified)$", re.I)},
        ) or soup.find("meta", property="article:modified_time")
        if updated_meta and updated_meta.get("content"):
            mod_date = MetadataParser.parse_iso_date(str(updated_meta["content"]))

        # 6. Extra metadata
        extra_metadata: dict[str, Any] = {}
        if description:
            extra_metadata["description"] = description

        keywords_meta = soup.find(
            "meta", attrs={"name": re.compile(r"^keywords$", re.I)}
        )
        if keywords_meta and keywords_meta.get("content"):
            keywords = [
                k.strip()
                for k in str(keywords_meta["content"]).split(",")
                if k.strip()
            ]
            extra_metadata["keywords"] = keywords

        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            extra_metadata["canonical_url"] = str(canonical["href"])

        return ExtractedMetadata(
            title=title,
            author=author,
            creation_date=creation_date,
            modification_date=mod_date,
            page_count=1,
            language=language,
            extra_metadata=extra_metadata,
        )

    def parse(self, content: bytes | Path) -> ExtractedDocument:
        """Execute single-pass parsing of HTML document."""
        raw_text = self.extract_text(content)
        metadata = self.extract_metadata(content)
        return ExtractedDocument(raw_text=raw_text, metadata=metadata)
