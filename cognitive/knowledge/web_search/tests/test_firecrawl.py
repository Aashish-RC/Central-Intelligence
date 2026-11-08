"""Unit tests for FirecrawlClient, Crawl4AI adapter, and top-level web_search.search."""

import json
from unittest.mock import MagicMock, patch
import pytest

import web_search
from web_search.core.provider import FirecrawlClient, Crawl4AiAdapter
from web_search.core.models import SearchResult, WebCitation


def test_top_level_web_search():
    result = web_search.search("python latest release", num_results=3)

    assert isinstance(result, SearchResult)
    assert len(result) > 0
    assert len(result.results) > 0
    assert len(result.citations) > 0
    assert isinstance(result.citations[0], WebCitation)
    assert result.citations[0].url.startswith("http")
    assert result.citations[0].domain != ""
    assert result.markdown_content != ""
    # Test iterator support
    assert any("python" in r.title.lower() or "python" in r.url.lower() for r in result)


def test_firecrawl_mock_api_search():
    client = FirecrawlClient(api_key="fc-test-key", base_url="https://api.firecrawl.dev")

    mock_resp_data = {
        "data": [
            {
                "title": "Python 3.14 Release Notes",
                "url": "https://docs.python.org/3.14/",
                "description": "Python 3.14 documentation and release notes",
                "markdown": "Python 3.14 includes major performance upgrades.",
            }
        ]
    }

    mock_cm = MagicMock()
    mock_cm.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
    mock_cm.__enter__.return_value = mock_cm

    with patch("urllib.request.urlopen", return_value=mock_cm) as mock_urlopen:
        res = client.search_and_extract("Python 3.14", num_results=1)
        assert len(res) == 1
        assert res[0].title == "Python 3.14 Release Notes"
        assert res[0].url == "https://docs.python.org/3.14/"
        assert len(res.citations) == 1
        assert res.citations[0].domain == "docs.python.org"
        assert "Python 3.14 documentation" in res.citations[0].quote_text


def test_firecrawl_mock_api_scrape():
    client = FirecrawlClient(api_key="fc-test-key", base_url="https://api.firecrawl.dev")

    mock_resp_data = {
        "data": {
            "markdown": "# Python 3.14\n\nNew Features in Python 3.14.",
            "metadata": {
                "title": "Python 3.14 Documentation",
                "links": ["https://python.org"],
            },
        }
    }

    mock_cm = MagicMock()
    mock_cm.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
    mock_cm.__enter__.return_value = mock_cm

    with patch("urllib.request.urlopen", return_value=mock_cm):
        page = client.scrape("https://docs.python.org/3.14/")
        assert page.title == "Python 3.14 Documentation"
        assert "# Python 3.14" in page.markdown_content
        assert len(page.content_sha256) == 64
        assert page.links == ["https://python.org"]


def test_crawl4ai_fallback_adapter():
    adapter = Crawl4AiAdapter()
    page = adapter.scrape(
        url="https://example.com/crawl",
        html_override="<html><head><title>Crawl Test</title></head><body><h1>Crawled Title</h1><p>Body text</p></body></html>",
    )
    assert page.title == "Crawl Test"
    assert "# Crawled Title" in page.markdown_content
