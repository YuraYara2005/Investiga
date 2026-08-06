"""Unit Tests for HTML Document Parser and Web Documentation Extraction.

Covers:
- HTML metadata extraction (title, description, language, author, dates, keywords)
- Removal of scripts, styles, navs, headers, footers, asides, and advertisements
- Preservation of headings, paragraphs, tables, lists, code blocks, and blockquotes
- Robust handling of malformed HTML, Unicode entities, and encoding variations
- Empty and large HTML document processing
- Parser factory selection and DocumentProcessor integration
"""

from app.document_processing import (
    DocumentParserFactory,
    DocumentProcessor,
    ExtractedDocument,
    HtmlParser,
)


def test_html_parser_supports_extensions_and_mimes() -> None:
    """Test HtmlParser format recognition."""
    parser = HtmlParser()
    assert parser.supports(".html") is True
    assert parser.supports(".htm") is True
    assert parser.supports(".HTML") is True
    assert parser.supports(".HTM") is True
    assert parser.supports("doc.html") is True
    assert parser.supports("page.htm") is True
    assert parser.supports(".pdf") is False
    assert parser.supports(".py") is False

    assert parser.supports("", mime_type="text/html") is True
    assert parser.supports("", mime_type="application/xhtml+xml") is True
    assert parser.supports("", mime_type="application/pdf") is False


def test_html_parser_metadata_extraction_comprehensive() -> None:
    """Test full metadata extraction from HTML <head> and OpenGraph / Twitter tags."""
    html_content = """<!DOCTYPE html>
<html lang="en-US">
<head>
    <meta charset="UTF-8">
    <title>Investiga Documentation - Architecture Guide</title>
    <meta name="description" content="Comprehensive architectural overview of Investiga RAG subsystem.">
    <meta name="author" content="Platform Engineering Team">
    <meta name="keywords" content="RAG, search, vector, AI, investigation">
    <meta name="date" content="2026-08-01T10:00:00Z">
    <meta name="last-modified" content="2026-08-05T15:30:00Z">
    <link rel="canonical" href="https://docs.investiga.internal/architecture">
</head>
<body>
    <main>
        <h1>System Architecture</h1>
        <p>Investiga combines vector search with neural reranking.</p>
    </main>
</body>
</html>"""

    parser = HtmlParser()
    extracted: ExtractedDocument = parser.parse(html_content.encode("utf-8"))

    meta = extracted.metadata
    assert meta.title == "Investiga Documentation - Architecture Guide"
    assert meta.author == "Platform Engineering Team"
    assert meta.language == "en"
    assert meta.creation_date is not None
    assert meta.creation_date.year == 2026
    assert meta.creation_date.month == 8
    assert meta.creation_date.day == 1
    assert meta.modification_date is not None
    assert meta.modification_date.day == 5
    assert meta.extra_metadata.get("description") == (
        "Comprehensive architectural overview of Investiga RAG subsystem."
    )
    assert "RAG" in meta.extra_metadata.get("keywords", [])
    assert meta.extra_metadata.get("canonical_url") == "https://docs.investiga.internal/architecture"


def test_html_parser_fallback_title_from_h1() -> None:
    """Test title resolution when <title> tag is missing."""
    html_content = """<html>
<body>
    <h1>Incident Management Runbook</h1>
    <p>Step-by-step triage guide.</p>
</body>
</html>"""
    parser = HtmlParser()
    extracted = parser.parse(html_content.encode("utf-8"))
    assert extracted.metadata.title == "Incident Management Runbook"


def test_html_parser_removes_boilerplate_and_ads() -> None:
    """Test stripping of scripts, styles, navigation, headers, footers, asides, and ads."""
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Article with Ads</title>
    <style>body { background: #fff; } .ad-banner { display: block; }</style>
    <script>console.log("tracking pixel");</script>
</head>
<body>
    <header>
        <div class="logo">Investiga</div>
        <nav>
            <a href="/home">Home</a>
            <a href="/docs">Docs</a>
        </nav>
    </header>

    <aside class="sidebar">
        <h3>Related Links</h3>
        <p>Sidebar navigation content</p>
    </aside>

    <div class="ad-container ad-banner sponsor-box" id="google-ad-123" role="banner">
        <p>Buy our sponsored security product!</p>
    </div>

    <ins class="adsbygoogle" style="display:block"></ins>

    <main>
        <h1>Core Investigation Workflow</h1>
        <p>Primary investigative report content that should be preserved.</p>
    </main>

    <footer>
        <p>Copyright 2026 Investiga Inc. All rights reserved.</p>
    </footer>
</body>
</html>"""

    parser = HtmlParser()
    extracted = parser.parse(html_content.encode("utf-8"))
    text = extracted.raw_text

    # Boilerplate removed
    assert "console.log" not in text
    assert "background: #fff" not in text
    assert "Sidebar navigation" not in text
    assert "Buy our sponsored security product" not in text
    assert "Copyright 2026" not in text

    # Core content preserved
    assert "# Core Investigation Workflow" in text
    assert "Primary investigative report content that should be preserved." in text


def test_html_parser_preserves_structural_elements() -> None:
    """Test preservation of headings, tables, ordered/unordered lists, code blocks, blockquotes."""
    html_content = """<!DOCTYPE html>
<html>
<head><title>Technical Spec</title></head>
<body>
    <h1>API Specification</h1>
    <h2>Authentication</h2>
    <p>All requests require a bearer token in the <code>Authorization</code> header.</p>

    <blockquote>Security note: Rotate JWT keys every 30 days.</blockquote>

    <h3>Supported Endpoints</h3>
    <ul>
        <li>POST /api/v1/auth/token</li>
        <li>GET /api/v1/knowledge/query</li>
    </ul>

    <h3>Deployment Steps</h3>
    <ol>
        <li>Build docker image</li>
        <li>Apply migration</li>
        <li>Restart pod</li>
    </ol>

    <h3>Query Parameters</h3>
    <table>
        <thead>
            <tr><th>Param</th><th>Type</th><th>Description</th></tr>
        </thead>
        <tbody>
            <tr><td>limit</td><td>integer</td><td>Max records</td></tr>
            <tr><td>filter</td><td>string</td><td>Query filter</td></tr>
        </tbody>
    </table>

    <h3>Sample Code</h3>
    <pre><code class="language-python">import httpx

async def fetch_data():
    response = await httpx.get("https://api.internal/data")
    return response.json()
</code></pre>
</body>
</html>"""

    parser = HtmlParser()
    extracted = parser.parse(html_content.encode("utf-8"))
    text = extracted.raw_text

    # Headings
    assert "# API Specification" in text
    assert "## Authentication" in text
    assert "### Supported Endpoints" in text

    # Paragraph with inline code
    assert "`Authorization`" in text

    # Blockquote
    assert "> Security note: Rotate JWT keys every 30 days." in text

    # Unordered list
    assert "- POST /api/v1/auth/token" in text
    assert "- GET /api/v1/knowledge/query" in text

    # Ordered list
    assert "1. Build docker image" in text
    assert "2. Apply migration" in text
    assert "3. Restart pod" in text

    # Table
    assert "| Param | Type | Description |" in text
    assert "| limit | integer | Max records |" in text
    assert "| filter | string | Query filter |" in text

    # Code block with language
    assert "```python" in text
    assert "import httpx" in text
    assert "async def fetch_data():" in text


def test_html_parser_malformed_html() -> None:
    """Test parser tolerance against badly structured or broken HTML."""
    malformed_html = """<html>
<head><title>Broken Page
<body>
    <h1>Title with no closing h1
    <p>Paragraph 1 <b>bold without end
    <div><span>Unclosed tags everywhere
    <table><tr><td>Cell 1<td>Cell 2<tr><td>Cell 3<td>Cell 4</table>
"""
    parser = HtmlParser()
    extracted = parser.parse(malformed_html.encode("utf-8"))

    assert extracted.metadata.title is not None
    assert "Broken Page" in extracted.metadata.title or "Title with no closing h1" in extracted.metadata.title
    assert "Paragraph 1" in extracted.raw_text
    assert "Cell 1" in extracted.raw_text
    assert "Cell 4" in extracted.raw_text


def test_html_parser_unicode_entities_and_accents() -> None:
    """Test unescaping of HTML entities and multibyte Unicode preservation."""
    html_content = """<html>
<head><title>Événement &amp; Sécurité</title></head>
<body>
    <h1>Analyse d&#39;incident &gt; Gravité Haute</h1>
    <p>&quot;Investiga&quot; supporte les caractères accentués: é, è, à, ç, ü, ñ, 日本語, 🚀.</p>
</body>
</html>"""

    parser = HtmlParser()
    extracted = parser.parse(html_content.encode("utf-8"))

    assert extracted.metadata.title == "Événement & Sécurité"
    assert "Analyse d'incident > Gravité Haute" in extracted.raw_text
    assert '"Investiga"' in extracted.raw_text
    assert "accentués: é, è, à, ç, ü, ñ, 日本語, 🚀" in extracted.raw_text


def test_html_parser_empty_and_whitespace_files() -> None:
    """Test handling of empty or blank HTML payloads."""
    parser = HtmlParser()

    # Completely empty bytes
    extracted_empty = parser.parse(b"")
    assert extracted_empty.raw_text == ""
    assert extracted_empty.metadata.page_count == 1

    # Whitespace only
    extracted_ws = parser.parse(b"   \n\t   ")
    assert extracted_ws.raw_text == ""

    # Empty tags only
    extracted_tags = parser.parse(b"<html><head></head><body></body></html>")
    assert extracted_tags.raw_text == ""


def test_html_parser_large_file() -> None:
    """Test parsing a large multi-section technical documentation page."""
    sections: list[str] = []
    sections.append("<html><head><title>Massive Documentation</title></head><body>")
    for i in range(100):
        sections.append(f"<h2>Section {i}</h2>")
        sections.append(f"<p>This is paragraph {i} detailing system telemetry and operational protocols.</p>")
        sections.append(
            f"<table><tr><th>Metric</th><th>Val</th></tr><tr><td>CPU_{i}</td><td>{i*10}%</td></tr></table>"
        )
    sections.append("</body></html>")
    large_html = "\n".join(sections)

    parser = HtmlParser()
    extracted = parser.parse(large_html.encode("utf-8"))

    assert extracted.metadata.title == "Massive Documentation"
    assert "## Section 0" in extracted.raw_text
    assert "## Section 99" in extracted.raw_text
    assert "| CPU_99 | 990% |" in extracted.raw_text


def test_html_parser_factory_and_processor_integration() -> None:
    """Test resolution via DocumentParserFactory and execution through DocumentProcessor."""
    factory = DocumentParserFactory()
    parser = factory.get_parser("guide.html")
    assert isinstance(parser, HtmlParser)

    parser_htm = factory.get_parser("index.htm")
    assert isinstance(parser_htm, HtmlParser)

    processor = DocumentProcessor(parser_factory=factory)
    raw_html = (
        "<html><head><title>FastAPI Docs</title></head>"
        "<body><h1>FastAPI Overview</h1><p>High performance web framework.</p></body></html>"
    )

    result = processor.process_sync(
        content=raw_html.encode("utf-8"),
        filename="fastapi.html",
        language="en",
    )

    assert result.title == "FastAPI Docs"
    assert result.language == "en"
    assert "# FastAPI Overview" in result.clean_text
    assert result.word_count > 0
    assert result.processing_time_ms >= 0.0
