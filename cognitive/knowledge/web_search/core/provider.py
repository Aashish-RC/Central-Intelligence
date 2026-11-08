"""Firecrawl and Crawl4AI Real Scraper and Search Adapters."""

import hashlib
import json
import os
import urllib.parse
import urllib.request
from typing import List, Optional
from urllib.parse import urlparse

from .interfaces import BaseWebScraper, BaseWebSearchProvider
from .models import ScrapedPage, SearchResult, WebCitation, WebSearchResultItem, utc_now
from ..scraper.crawler import PoliteCrawler
from ..scraper.parser import HTMLMarkdownParser
from ..providers.duckduckgo import DuckDuckGoSearchProvider
from ..providers.mock_provider import MockWebSearchProvider


class Crawl4AiAdapter(BaseWebScraper):
    """Crawl4AI scraper adapter with automatic fallback to PoliteCrawler."""

    def __init__(self, fallback_scraper: Optional[BaseWebScraper] = None):
        self._fallback = fallback_scraper or PoliteCrawler()

    def scrape(self, url: str, html_override: Optional[str] = None) -> ScrapedPage:
        if html_override is not None:
            return HTMLMarkdownParser.parse_html(html_override, url=url)

        # Attempt to use crawl4ai if installed in current environment
        try:
            import importlib
            crawl4ai_mod = importlib.import_module("crawl4ai")
            # If WebCrawler or AsyncWebCrawler is present
            if hasattr(crawl4ai_mod, "WebCrawler"):
                crawler = crawl4ai_mod.WebCrawler()
                crawler.warmup()
                result = crawler.run(url=url)
                md = getattr(result, "markdown", "") or ""
                sha = hashlib.sha256(md.encode("utf-8")).hexdigest()
                return ScrapedPage(
                    url=url,
                    title=getattr(result, "title", "") or url,
                    markdown_content=md,
                    clean_text=getattr(result, "cleaned_text", "") or md,
                    content_sha256=sha,
                    links=[],
                    retrieved_at=utc_now(),
                )
        except Exception:
            pass

        return self._fallback.scrape(url=url, html_override=html_override)


class FirecrawlClient(BaseWebSearchProvider, BaseWebScraper):
    """Production Firecrawl API client connecting to https://api.firecrawl.dev with Crawl4AI / Polite fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.firecrawl.dev",
        timeout: float = 8.0,
        fallback_scraper: Optional[BaseWebScraper] = None,
        fallback_provider: Optional[BaseWebSearchProvider] = None,
    ):
        self._api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        self._base_url = (base_url or "https://api.firecrawl.dev").rstrip("/")
        self._timeout = timeout
        self._scraper = fallback_scraper or Crawl4AiAdapter()
        self._search_provider = fallback_provider or DuckDuckGoSearchProvider()

    def search(self, query: str, num_results: int = 5) -> List[WebSearchResultItem]:
        """Search the web via Firecrawl /v1/search API or fallback provider."""
        if self._api_key:
            try:
                endpoint = f"{self._base_url}/v1/search"
                payload = json.dumps({"query": query, "limit": num_results}).encode("utf-8")
                req = urllib.request.Request(
                    endpoint,
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "Pheonix-WebSearch/1.0",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    hits = data.get("data", []) or data.get("results", [])
                    results: List[WebSearchResultItem] = []
                    for h in hits[:num_results]:
                        url = h.get("url") or ""
                        results.append(
                            WebSearchResultItem(
                                title=h.get("title") or query,
                                url=url,
                                snippet=h.get("description") or h.get("markdown", "")[:200],
                                domain=urlparse(url).netloc or "firecrawl.dev",
                                published_date=h.get("metadata", {}).get("publishedDate"),
                            )
                        )
                    if results:
                        return results
            except Exception:
                pass

        return self._search_provider.search(query=query, num_results=num_results)

    def scrape(self, url: str, html_override: Optional[str] = None) -> ScrapedPage:
        """Scrape webpage via Firecrawl /v1/scrape or fallback scraper."""
        if html_override is not None:
            return self._scraper.scrape(url=url, html_override=html_override)

        if self._api_key:
            try:
                endpoint = f"{self._base_url}/v1/scrape"
                payload = json.dumps({"url": url, "formats": ["markdown"]}).encode("utf-8")
                req = urllib.request.Request(
                    endpoint,
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "Pheonix-WebSearch/1.0",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    page_data = data.get("data", {})
                    md = page_data.get("markdown", "") or ""
                    sha = hashlib.sha256(md.encode("utf-8")).hexdigest()
                    meta = page_data.get("metadata", {})
                    title = meta.get("title") or url
                    return ScrapedPage(
                        url=url,
                        title=title,
                        markdown_content=md,
                        clean_text=md,
                        content_sha256=sha,
                        links=meta.get("links", []),
                        retrieved_at=utc_now(),
                    )
            except Exception:
                pass

        return self._scraper.scrape(url=url, html_override=html_override)

    def search_and_extract(self, query: str, num_results: int = 5) -> SearchResult:
        """Search and synthesize structured citations and parsed markdown content."""
        hits = self.search(query=query, num_results=num_results)
        citations: List[WebCitation] = []
        md_chunks: List[str] = []

        for hit in hits:
            # Build citation from hit snippet
            snippet_clean = hit.snippet.strip()
            sha = hashlib.sha256((snippet_clean or hit.url).encode("utf-8")).hexdigest()
            cit = WebCitation(
                url=hit.url,
                domain=hit.domain or urlparse(hit.url).netloc,
                title=hit.title,
                quote_text=snippet_clean or hit.title,
                content_sha256=sha,
                retrieved_at=utc_now(),
            )
            citations.append(cit)
            md_chunks.append(f"### [{hit.title}]({hit.url})\n\n{snippet_clean}\n")

        return SearchResult(
            query=query,
            results=hits,
            citations=citations,
            markdown_content="\n".join(md_chunks),
        )


def search(
    query: str,
    num_results: int = 5,
    api_key: Optional[str] = None,
    base_url: str = "https://api.firecrawl.dev",
) -> SearchResult:
    """Top-level convenience search helper returning parsed web content and populated citations."""
    client = FirecrawlClient(api_key=api_key, base_url=base_url)
    return client.search_and_extract(query=query, num_results=num_results)
