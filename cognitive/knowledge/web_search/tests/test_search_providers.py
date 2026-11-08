"""Unit tests for web search provider adapters and normalization."""

import pytest
from web_search.providers.mock_provider import MockWebSearchProvider
from web_search.providers.duckduckgo import DuckDuckGoSearchProvider


def test_mock_search_provider_queries():
    provider = MockWebSearchProvider()

    # Query 1: Python release notes
    results = provider.search("Python 3.14 features", num_results=2)
    assert len(results) <= 2
    assert any("Python 3.14" in r.title for r in results)
    assert results[0].domain == "docs.python.org"
    assert results[0].url.startswith("https://docs.python.org")

    # Query 2: Cryptographic AES
    crypto_results = provider.search("AES-256-GCM encryption", num_results=1)
    assert len(crypto_results) == 1
    assert "AES-256-GCM" in crypto_results[0].title
    assert crypto_results[0].domain == "csrc.nist.gov"


def test_duckduckgo_provider_fallback():
    ddg = DuckDuckGoSearchProvider()
    results = ddg.search("FastAPI framework benchmarks", num_results=3)
    assert len(results) >= 1
    assert any("FastAPI" in r.title or "FastAPI" in r.snippet for r in results)
