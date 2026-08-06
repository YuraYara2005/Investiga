"""Unit Tests for Source Code Parser across Software Repositories.

Covers:
- Language detection across 20+ programming languages and Dockerfiles
- Shebang and syntax-based language inference
- Preservation of code indentation, structural whitespace, comments, and class/function boundaries
- Accurate line counting and structural metadata calculation
- Multi-encoding and Unicode handling (multilingual comments, string literals)
- Empty, whitespace, and large code files
- Factory resolution and DocumentProcessor integration
"""

from app.document_processing import (
    DocumentParserFactory,
    DocumentProcessor,
    SourceCodeParser,
)


def test_source_code_parser_supports_all_languages() -> None:
    """Test format recognition for all requested programming language extensions and Dockerfile."""
    parser = SourceCodeParser()

    supported_samples = [
        "app.py",
        "script.pyw",
        "index.js",
        "module.mjs",
        "config.cjs",
        "main.ts",
        "types.mts",
        "component.jsx",
        "App.tsx",
        "Main.java",
        "driver.c",
        "engine.cpp",
        "header.h",
        "types.hpp",
        "Program.cs",
        "server.go",
        "lib.rs",
        "Application.kt",
        "Model.swift",
        "index.php",
        "schema.sql",
        "deploy.sh",
        "setup.bash",
        "script.ps1",
        "Dockerfile",
        "Dockerfile.prod",
        "Dockerfile.dev",
        ".dockerfile",
    ]

    for filename in supported_samples:
        assert parser.supports(filename) is True, f"Failed for {filename}"

    assert parser.supports(".pdf") is False
    assert parser.supports(".docx") is False
    assert parser.supports(".exe") is False


def test_source_code_parser_metadata_and_language_detection() -> None:
    """Test accurate detection of programming languages and line count metadata."""
    parser = SourceCodeParser()

    # 1. Python
    py_code = """# Core Service Implementation
import os
from typing import Optional

class AuthService:
    \"\"\"Handles user authentication and JWT validation.\"\"\"

    def __init__(self, secret_key: str) -> None:
        self.secret_key = secret_key

    def verify_token(self, token: str) -> bool:
        # Token validation routine
        return bool(token and len(token) > 10)
"""
    extracted_py = parser.parse(py_code.encode("utf-8"))
    meta_py = extracted_py.metadata
    assert meta_py.language == "python"
    assert meta_py.extra_metadata["detected_language"] == "python"
    assert meta_py.extra_metadata["line_count"] == 13
    assert meta_py.extra_metadata["has_comments"] is True
    assert meta_py.extra_metadata["character_count"] == len(py_code)

    # 2. Rust
    rust_code = """// Memory-safe buffer manager
pub struct BufferPool {
    capacity: usize,
}

impl BufferPool {
    pub fn new(capacity: usize) -> Self {
        BufferPool { capacity }
    }
}
"""
    meta_rs = parser.extract_metadata(rust_code.encode("utf-8"), filename="pool.rs")
    assert meta_rs.language == "rust"
    assert meta_rs.extra_metadata["detected_language"] == "rust"
    assert meta_rs.extra_metadata["has_comments"] is True

    # 3. Go
    go_code = """package main

import "fmt"

// Main entry point
func main() {
    fmt.Println("Investiga Engine Initialized")
}
"""
    meta_go = parser.extract_metadata(go_code.encode("utf-8"), filename="main.go")
    assert meta_go.language == "go"
    assert meta_go.extra_metadata["detected_language"] == "go"

    # 4. TypeScript / TSX
    tsx_code = """import React from 'react';

interface Props {
  title: string;
}

export const Header: React.FC<Props> = ({ title }) => {
  return <h1>{title}</h1>;
};
"""
    meta_tsx = parser.extract_metadata(tsx_code.encode("utf-8"), filename="Header.tsx")
    assert meta_tsx.language == "tsx"


def test_source_code_parser_dockerfile_handling() -> None:
    """Test Dockerfile parsing and language inference."""
    parser = SourceCodeParser()
    dockerfile_content = """# Multi-stage build for Investiga Backend
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runner
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
    extracted = parser.parse(dockerfile_content.encode("utf-8"))
    assert extracted.metadata.language == "dockerfile"
    assert extracted.metadata.extra_metadata["has_comments"] is True
    assert "FROM python:3.12-slim" in extracted.raw_text
    assert "CMD [\"uvicorn\"" in extracted.raw_text


def test_source_code_parser_shebang_inference() -> None:
    """Test language detection from shebang header when extension is missing or generic."""
    parser = SourceCodeParser()

    # Python shebang
    py_script = "#!/usr/bin/env python3\nprint('Hello from Python script')"
    meta = parser.extract_metadata(py_script.encode("utf-8"))
    assert meta.language == "python"

    # Bash shebang
    sh_script = "#!/bin/bash\necho 'Deploying cluster...'"
    meta_sh = parser.extract_metadata(sh_script.encode("utf-8"))
    assert meta_sh.language == "shell"

    # Node shebang
    node_script = "#!/usr/bin/env node\nconsole.log('Running CLI');"
    meta_node = parser.extract_metadata(node_script.encode("utf-8"))
    assert meta_node.language == "javascript"


def test_source_code_parser_preserves_indentation_and_comments() -> None:
    """Test strict preservation of nested indentation, docstrings, and multiple comment styles."""
    parser = SourceCodeParser()

    code = """def complex_algorithm(matrix: list[list[int]]) -> int:
    \"\"\"Multi-line docstring with formatting intact.\"\"\"
    total = 0
    # Process rows
    for i, row in enumerate(matrix):
        # Process columns
        for j, val in enumerate(row):
            if val > 0:
                total += val * 2
            else:
                total -= 1
    return total
"""
    extracted = parser.parse(code.encode("utf-8"))
    raw = extracted.raw_text

    # Indentation preserved exactly
    assert "    total = 0" in raw
    assert "        for j, val in enumerate(row):" in raw
    assert "                total += val * 2" in raw

    # Comments & docstrings preserved
    assert '"""Multi-line docstring with formatting intact."""' in raw
    assert "# Process rows" in raw
    assert "# Process columns" in raw


def test_source_code_parser_unicode_in_code() -> None:
    """Test unicode characters in comments, string literals, and identifiers."""
    parser = SourceCodeParser()
    code = """// Multilingual comments: 認証トークン, 인증, Безопасность
const welcomeMessage = "Bienvenue à l'outil Investiga 🔍 🚀";
const piSymbol = "π ≈ 3.14159";
"""
    extracted = parser.parse(code.encode("utf-8"))
    assert "認証トークン, 인증, Безопасность" in extracted.raw_text
    assert "Bienvenue à l'outil Investiga 🔍 🚀" in extracted.raw_text
    assert "π ≈ 3.14159" in extracted.raw_text


def test_source_code_parser_empty_and_whitespace_files() -> None:
    """Test handling of empty, whitespace, and comment-only code files."""
    parser = SourceCodeParser()

    # Empty payload
    empty_res = parser.parse(b"")
    assert empty_res.raw_text == ""
    assert empty_res.metadata.extra_metadata["line_count"] == 0

    # Whitespace only
    ws_res = parser.parse(b"   \n\t\n   ")
    assert ws_res.raw_text == ""

    # Comment only
    comment_only = parser.parse(b"// Just a comment\n// Line 2")
    assert comment_only.metadata.extra_metadata["has_comments"] is True
    assert "// Just a comment" in comment_only.raw_text


def test_source_code_parser_large_file() -> None:
    """Test parsing of large 1500+ line source file."""
    lines: list[str] = ["// Large code file generator"]
    for i in range(500):
        lines.append(f"class Worker_{i} {{")
        lines.append(f"    public execute_{i}(): number {{")
        lines.append(f"        // Computing metric {i}")
        lines.append(f"        return {i} * 42;")
        lines.append("    }")
        lines.append("}")
    large_code = "\n".join(lines)

    parser = SourceCodeParser()
    extracted = parser.parse(large_code.encode("utf-8"))

    assert extracted.metadata.extra_metadata["line_count"] > 1500
    assert "class Worker_0 {" in extracted.raw_text
    assert "class Worker_499 {" in extracted.raw_text


def test_source_code_parser_factory_resolution_and_processor() -> None:
    """Test resolution via DocumentParserFactory and end-to-end processing via DocumentProcessor."""
    factory = DocumentParserFactory()

    # Test parser factory resolution for various code languages
    assert isinstance(factory.get_parser("main.py"), SourceCodeParser)
    assert isinstance(factory.get_parser("index.ts"), SourceCodeParser)
    assert isinstance(factory.get_parser("query.sql"), SourceCodeParser)
    assert isinstance(factory.get_parser("Dockerfile"), SourceCodeParser)
    assert isinstance(factory.get_parser("Dockerfile.prod"), SourceCodeParser)

    # Test DocumentProcessor execution
    processor = DocumentProcessor(parser_factory=factory)
    py_content = b"def calculate_risk(score: float) -> str:\n    return 'HIGH' if score > 0.8 else 'LOW'\n"

    result = processor.process_sync(
        content=py_content,
        filename="risk_calc.py",
    )

    assert result.title == "risk_calc"
    assert result.word_count > 0
    assert "def calculate_risk" in result.clean_text
    assert result.processing_time_ms >= 0.0
