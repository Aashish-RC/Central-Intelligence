"""
Unit tests for Crawl4AI Web & Document Adapter (Layer 1: Perception, Task 1.3).
"""

from pathlib import Path
import pytest
from cognitive.perception.document.crawl4ai_adapter import (
    Crawl4AIAdapter,
    CrawlResult,
)


@pytest.fixture
def sample_html() -> str:
    return """<!DOCTYPE html>
<html>
<head>
    <title>Central Intelligence Architecture Guide</title>
    <style>.nav { color: red; }</style>
    <script>alert("ignore script");</script>
</head>
<body>
    <header><nav>Home | Docs | Login</nav></header>
    <h1>Perception Layer Specification</h1>
    <p>The Perception Layer provides multi-modal input ingestion across all sensory interfaces.</p>
    <h2>Supported Features</h2>
    <ul>
        <li>Real-time WebRTC audio</li>
        <li>Offline speech dictation</li>
        <li>Dynamic web ingestion with Crawl4AI</li>
    </ul>
    <h2>Performance Benchmarks</h2>
    <table>
        <tr>
            <th>Module</th>
            <th>Target Latency</th>
            <th>Status</th>
        </tr>
        <tr>
            <td>LiveKit WebRTC</td>
            <td>&lt;100ms</td>
            <td>Passed</td>
        </tr>
        <tr>
            <td>Handy Offline STT</td>
            <td>&lt;500ms</td>
            <td>Passed</td>
        </tr>
    </table>
    <a href="https://docs.central-intelligence.org/specs">Read Full Documentation</a>
</body>
</html>
"""


def test_html_to_markdown_clean_conversion(sample_html: str):
    """Verify HTML cleaning, table formatting, and markdown generation."""
    adapter = Crawl4AIAdapter()
    result = adapter.html_to_markdown(sample_html, url="https://internal.test/docs")

    assert isinstance(result, CrawlResult)
    assert result.is_success is True
    assert result.title == "Central Intelligence Architecture Guide"

    # Verify scripts, styles, and nav are removed
    assert "alert(" not in result.markdown
    assert ".nav {" not in result.markdown
    assert "Home | Docs | Login" not in result.markdown

    # Verify markdown headers and lists
    assert "# Perception Layer Specification" in result.markdown
    assert "## Supported Features" in result.markdown
    assert "- Real-time WebRTC audio" in result.markdown

    # Verify table conversion to GFM
    assert len(result.extracted_tables) == 1
    assert "| Module | Target Latency | Status |" in result.markdown
    assert "| LiveKit WebRTC | <100ms | Passed |" in result.markdown

    # Verify link extraction
    assert "https://docs.central-intelligence.org/specs" in result.links


@pytest.mark.asyncio
async def test_crawl_local_file_url(tmp_path: Path, sample_html: str):
    """Acceptance: Can fetch a URL and return clean markdown."""
    adapter = Crawl4AIAdapter()
    test_page = tmp_path / "index.html"
    test_page.write_text(sample_html, encoding="utf-8")

    file_url = f"file://{test_page.resolve()}"
    result = await adapter.crawl_url(file_url)

    assert result.is_success is True
    assert "# Perception Layer Specification" in result.markdown
    assert "| LiveKit WebRTC | <100ms | Passed |" in result.markdown


def test_crawl_url_sync_wrapper(tmp_path: Path, sample_html: str):
    """Verify synchronous crawl method."""
    adapter = Crawl4AIAdapter()
    test_page = tmp_path / "doc.html"
    test_page.write_text(sample_html, encoding="utf-8")

    result = adapter.crawl_url_sync(str(test_page.resolve()))
    assert result.is_success is True
    assert "The Perception Layer provides multi-modal input ingestion" in result.markdown


@pytest.mark.asyncio
async def test_crawl_error_handling():
    """Verify error reporting on missing local path."""
    adapter = Crawl4AIAdapter()
    res = await adapter.crawl_url("file:///nonexistent/path/page.html")
    assert res.status_code == 404
    assert res.is_success is False

