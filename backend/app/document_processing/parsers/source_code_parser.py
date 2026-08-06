"""Source Code Document Parser for Software Repositories and Codebases.

Extracts structured source code text preserving syntax formatting, indentation,
comments, structural whitespace, and class/function boundaries across multiple
programming languages without AST parsing overhead.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePath
from typing import Any, ClassVar

from app.core.logging import get_logger
from app.document_processing.models import ExtractedDocument, ExtractedMetadata
from app.document_processing.parsers.base_parser import BaseDocumentParser

logger = get_logger(__name__)

# Pre-compiled regex patterns
_LINE_ENDINGS_REGEX = re.compile(r"\r\n|\r")
_EXCESSIVE_BLANKS_REGEX = re.compile(r"\n{4,}")
_SHEBANG_REGEX = re.compile(r"^#!\s*/\S*?(python|node|bash|sh|zsh|perl|ruby|php|pwsh)")
_COMMENT_PATTERNS = re.compile(
    r"(?m)(^\s*#|^\s*//|/\*|^\s*--|^\s*;\s*|^\s*\(\*|^\s*<!--|^\s*\"\"\"|^\s*\'\'\')"
)


class SourceCodeParser(BaseDocumentParser):
    """Parser for source code files across major programming languages and Dockerfiles."""

    EXTENSION_TO_LANGUAGE: ClassVar[dict[str, str]] = {
        ".py": "python",
        ".pyw": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".mts": "typescript",
        ".cts": "typescript",
        ".jsx": "jsx",
        ".tsx": "tsx",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".h": "c_header",
        ".hpp": "cpp_header",
        ".hxx": "cpp_header",
        ".cs": "csharp",
        ".go": "go",
        ".rs": "rust",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".swift": "swift",
        ".php": "php",
        ".sql": "sql",
        ".sh": "shell",
        ".bash": "shell",
        ".zsh": "shell",
        ".ps1": "powershell",
        ".psm1": "powershell",
        ".dockerfile": "dockerfile",
        "dockerfile": "dockerfile",
    }

    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = set(EXTENSION_TO_LANGUAGE.keys())

    SUPPORTED_MIME_TYPES: ClassVar[set[str]] = {
        "text/x-python",
        "application/x-python-code",
        "text/javascript",
        "application/javascript",
        "application/x-javascript",
        "text/typescript",
        "application/typescript",
        "text/jsx",
        "text/tsx",
        "text/x-java-source",
        "text/x-java",
        "text/x-c",
        "text/x-c++",
        "text/x-csrc",
        "text/x-chdr",
        "text/x-c++src",
        "text/x-c++hdr",
        "text/x-csharp",
        "text/x-go",
        "text/x-rust",
        "text/x-rustsrc",
        "text/x-kotlin",
        "text/x-swift",
        "text/x-php",
        "application/x-httpd-php",
        "text/x-sql",
        "application/sql",
        "text/x-sh",
        "application/x-sh",
        "text/x-shellscript",
        "text/x-powershell",
        "application/x-powershell",
        "text/x-dockerfile",
    }

    def supports(self, extension: str, mime_type: str | None = None) -> bool:
        """Check if parser supports the given extension, filename or MIME type."""
        ext_clean = extension.lower().strip()
        if ext_clean in self.SUPPORTED_EXTENSIONS:
            return True

        path_obj = PurePath(ext_clean)
        if path_obj.name in {"dockerfile"} or path_obj.name.startswith("dockerfile."):
            return True

        suffix = path_obj.suffix
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

    def _detect_language(
        self,
        content_path_or_name: str | None,
        raw_text: str,
    ) -> str:
        """Infer programming language from file extension, filename, shebang, or syntax cues."""
        if content_path_or_name:
            path_obj = PurePath(content_path_or_name)
            name_lower = path_obj.name.lower()

            if name_lower == "dockerfile" or name_lower.startswith("dockerfile."):
                return "dockerfile"

            suffix = path_obj.suffix.lower()
            if suffix in self.EXTENSION_TO_LANGUAGE:
                return self.EXTENSION_TO_LANGUAGE[suffix]

        # Check shebang line if available
        first_line = raw_text.split("\n", 1)[0] if raw_text else ""
        if first_line.startswith("#!"):
            fl_lower = first_line.lower()
            if "python" in fl_lower:
                return "python"
            if "node" in fl_lower or "deno" in fl_lower or "bun" in fl_lower:
                return "javascript"
            if "bash" in fl_lower or "sh" in fl_lower or "zsh" in fl_lower:
                return "shell"
            if "pwsh" in fl_lower or "powershell" in fl_lower:
                return "powershell"
            if "php" in fl_lower:
                return "php"
            if "perl" in fl_lower:
                return "perl"
            if "ruby" in fl_lower:
                return "ruby"

        # Check Dockerfile syntax signature
        if re.search(r"(?m)^\s*(FROM|ARG|ENV|RUN|COPY|WORKDIR|ENTRYPOINT|CMD)\s+", raw_text):
            return "dockerfile"

        # Check Go syntax signature
        if re.search(r"(?m)^\s*(package\s+\w+|func\s+(\(\w+\s+\*?\w+\)\s+)?\w+)", raw_text):
            return "go"

        # Check Rust syntax signature
        if re.search(r"(?m)^\s*(fn\s+\w+|pub\s+(fn|struct|enum|trait|impl)|use\s+\w+::|impl\s+)", raw_text):
            return "rust"

        # Check Python syntax signature
        if re.search(r"(?m)^\s*(def\s+\w+|class\s+\w+|import\s+\w+|from\s+\w+\s+import|async\s+def\s+\w+)", raw_text):
            return "python"

        # Check SQL syntax signature
        if re.search(r"(?i)(?m)^\s*(SELECT\s+[\s\S]*?\s+FROM|CREATE\s+TABLE|INSERT\s+INTO|ALTER\s+TABLE)", raw_text):
            return "sql"

        # Check PHP syntax signature
        if re.search(r"(<\?php|\$[a-zA-Z_\x7f-\xff][a-zA-Z0-9_\x7f-\xff]*\s*=)", raw_text):
            return "php"

        # Check TypeScript / React syntax signature
        if re.search(r"(?m)^\s*(import\s+React|interface\s+\w+\s*\{|export\s+(default\s+)?(const|function|class|type))", raw_text):
            return "typescript"

        # Check Java syntax signature
        if re.search(r"(?m)^\s*(public\s+class\s+\w+|package\s+[\w.]+;|import\s+java[\w.]+;)", raw_text):
            return "java"

        # Check C# syntax signature
        if re.search(r"(?m)^\s*(using\s+System|namespace\s+\w+)", raw_text):
            return "csharp"

        # Check C / C++ syntax signature
        if re.search(r"(?m)^\s*(#include|int\s+main\s*\()", raw_text):
            return "cpp"

        # Check Shell script syntax signature
        if re.search(r"(?m)^\s*(echo\s+|export\s+\w+=|if\s+\[|fi\b)", raw_text):
            return "shell"

        return "text"

    def extract_text(self, content: bytes | Path) -> str:
        """Extract source code text preserving exact indentation, comments, and structure."""
        text = self._read_text(content)
        if not text:
            return ""

        # Normalize carriage returns to standard Unix \n
        normalized = _LINE_ENDINGS_REGEX.sub("\n", text)

        # Strip trailing whitespace on each line while strictly preserving indentation
        lines: list[str] = [line.rstrip() for line in normalized.split("\n")]
        joined = "\n".join(lines)

        # Collapse excessive consecutive blank lines (4+) to 2 to preserve clean vertical spacing
        cleaned = _EXCESSIVE_BLANKS_REGEX.sub("\n\n\n", joined)

        return cleaned.strip()

    def extract_metadata(
        self,
        content: bytes | Path,
        filename: str | None = None,
    ) -> ExtractedMetadata:
        """Extract code properties, estimated line count, detected language, and metadata."""
        text = self._read_text(content)
        file_hint = str(content) if isinstance(content, (str, Path)) else filename
        detected_lang = self._detect_language(file_hint, text)

        if not text.strip():
            return ExtractedMetadata(
                page_count=1,
                language=detected_lang,
                extra_metadata={
                    "detected_language": detected_lang,
                    "line_count": 0,
                    "character_count": 0,
                    "has_comments": False,
                },
            )

        lines = text.splitlines()
        line_count = len(lines)
        character_count = len(text)
        has_comments = bool(_COMMENT_PATTERNS.search(text))

        # Title: infer from filename stem if available
        title: str | None = None
        if file_hint:
            title = PurePath(file_hint).name

        extra_meta: dict[str, Any] = {
            "detected_language": detected_lang,
            "line_count": line_count,
            "character_count": character_count,
            "has_comments": has_comments,
            "estimated_token_count": max(1, character_count // 4),
        }

        return ExtractedMetadata(
            title=title,
            page_count=1,
            language=detected_lang,
            extra_metadata=extra_meta,
        )

    def parse(self, content: bytes | Path) -> ExtractedDocument:
        """Execute single-pass extraction of source code and structural metadata."""
        raw_text = self.extract_text(content)
        metadata = self.extract_metadata(content)
        return ExtractedDocument(raw_text=raw_text, metadata=metadata)
