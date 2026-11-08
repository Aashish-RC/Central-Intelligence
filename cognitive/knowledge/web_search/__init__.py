"""Pheonix Web Search, Polite Scraping, and Grounded Source-Support Citation Verification."""

from .core.models import (
    WebSearchResultItem,
    ScrapedPage,
    WebCitation,
    SourceSupportCheck,
    SearchResult,
)
from .providers.mock_provider import MockWebSearchProvider
from .providers.duckduckgo import DuckDuckGoSearchProvider
from .scraper.parser import HTMLMarkdownParser
from .scraper.crawler import PoliteCrawler
from .verifier.claim_checker import SourceSupportVerifier
from .core.provider import FirecrawlClient, Crawl4AiAdapter, search

__all__ = [
    "WebSearchResultItem",
    "ScrapedPage",
    "WebCitation",
    "SourceSupportCheck",
    "SearchResult",
    "MockWebSearchProvider",
    "DuckDuckGoSearchProvider",
    "HTMLMarkdownParser",
    "PoliteCrawler",
    "SourceSupportVerifier",
    "FirecrawlClient",
    "Crawl4AiAdapter",
    "search",
]
