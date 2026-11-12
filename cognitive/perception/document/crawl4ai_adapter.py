"""
Crawl4AI Web and Document Ingestion Adapter (Layer 1: Perception, Task 1.3).

Converts dynamic web pages, HTML content, and documents into clean, structured,
LLM-ready Markdown while extracting tables, links, and semantic metadata.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from control.safety.production_guard import (
    fail_closed_in_production,
    require_live_adapter,
)

logger = logging.getLogger("cognitive.perception.document.crawl4ai")

try:
    from crawl4ai import AsyncWebCrawler
    _CRAWL4AI_AVAILABLE = True
except ImportError:
    _CRAWL4AI_AVAILABLE = False


@dataclass
class CrawlResult:
    """Structured extraction result containing clean LLM-ready markdown."""
    url: str
    markdown: str
    title: str = ""
    status_code: int = 200
    links: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_tables: List[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300 and len(self.markdown.strip()) > 0


class Crawl4AIAdapter:
    """
    Web & document scraper converting pages to clean LLM-ready markdown (Task 1.3).
    Combines Crawl4AI browser automation with fast, resilient HTML/document parsers.
    """

    def __init__(
        self,
        headless: bool = True,
        user_agent: Optional[str] = None,
        timeout: float = 15.0,
        _defer_prod_check: bool = False,
    ) -> None:
        self.headless = headless
        self.user_agent = user_agent or "Central-Intelligence-Perception/1.0"
        self.timeout = timeout
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("crawl4ai")
        )

    def html_to_markdown(self, html: str, url: str = "") -> CrawlResult:
        """
        Parses raw HTML and transforms it into clean, noise-free Markdown.
        Strips scripts, styles, navigations, and converts semantic tags (h1-h6, p, ul, ol, table, a).
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text().strip() if title_tag else ""

        # Remove noise elements
        for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
            tag.decompose()

        # Extract links
        links: List[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href and not href.startswith("#") and not href.startswith("javascript:"):
                links.append(href)

        # Extract and convert tables
        extracted_tables: List[str] = []
        for table in soup.find_all("table"):
            table_md = self._table_to_markdown(table)
            if table_md:
                extracted_tables.append(table_md)
                table.replace_with(f"\n\n{table_md}\n\n")

        # Convert headers and text structure
        for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            level = int(h.name[1])
            h.replace_with(f"\n\n{'#' * level} {h.get_text().strip()}\n\n")

        for p in soup.find_all("p"):
            p.replace_with(f"\n\n{p.get_text().strip()}\n\n")

        for li in soup.find_all("li"):
            li.replace_with(f"\n- {li.get_text().strip()}")

        raw_text = soup.get_text()
        # Normalize whitespace and excessive blank lines
        clean_md = re.sub(r"\n{3,}", "\n\n", raw_text).strip()

        return CrawlResult(
            url=url,
            markdown=clean_md,
            title=title,
            status_code=200,
            links=links[:50],
            metadata={"parser": "crawl4ai_bs4_cleaner"},
            extracted_tables=extracted_tables,
        )

    def _table_to_markdown(self, table_soup: Any) -> str:
        """Converts an HTML table element to a clean GFM markdown table."""
        rows = table_soup.find_all("tr")
        if not rows:
            return ""

        table_data: List[List[str]] = []
        for row in rows:
            cols = [col.get_text().strip().replace("\n", " ") for col in row.find_all(["th", "td"])]
            if cols:
                table_data.append(cols)

        if not table_data:
            return ""

        # Normalize column counts
        max_cols = max(len(r) for r in table_data)
        for r in table_data:
            while len(r) < max_cols:
                r.append("")

        header = table_data[0]
        separator = ["---"] * max_cols
        md_lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        for data_row in table_data[1:]:
            md_lines.append("| " + " | ".join(data_row) + " |")

        return "\n".join(md_lines)

    async def crawl_url(self, url: str) -> CrawlResult:
        """
        Acceptance: Can fetch a URL and return clean markdown.
        Uses AsyncWebCrawler when available, with fast HTTP fallback for local / mock environments.
        """
        self.adapter_mode = require_live_adapter("crawl4ai")
        # 1. Check if file:// protocol
        if url.startswith("file://") or Path(url).exists():
            path_str = url[7:] if url.startswith("file://") else url
            path = Path(path_str)
            if not path.exists():
                return CrawlResult(url=url, markdown="", status_code=404)
            content = path.read_text(encoding="utf-8", errors="ignore")
            if path.suffix.lower() in (".html", ".htm"):
                return self.html_to_markdown(content, url=url)
            return CrawlResult(url=url, markdown=content, status_code=200)

        # 2. Try Crawl4AI AsyncWebCrawler if running in full browser mode
        if _CRAWL4AI_AVAILABLE:
            try:
                async with AsyncWebCrawler(headless=self.headless) as crawler:
                    res = await crawler.arun(url=url)
                    if res and res.markdown:
                        return CrawlResult(
                            url=url,
                            markdown=res.markdown.strip(),
                            title=getattr(res, "title", ""),
                            status_code=getattr(res, "status_code", 200) or 200,
                            metadata={"engine": "crawl4ai_playwright"},
                        )
            except Exception as e:
                logger.debug("AsyncWebCrawler failed, falling back to HTTP fetcher: %s", e)

        # 3. HTTP client fallback (fast, non-headless, deterministic)
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": self.user_agent})
                if resp.status_code >= 400:
                    return CrawlResult(
                        url=url,
                        markdown="",
                        status_code=resp.status_code,
                    )
                content_type = resp.headers.get("content-type", "")
                if "html" in content_type or "<html" in resp.text[:500].lower():
                    result = self.html_to_markdown(resp.text, url=url)
                    result.status_code = resp.status_code
                    return result
                return CrawlResult(
                    url=url,
                    markdown=resp.text.strip(),
                    status_code=resp.status_code,
                )
        except Exception as e:
            logger.warning("Failed fetching %s: %s", url, e)
            return CrawlResult(url=url, markdown="", status_code=500, metadata={"error": str(e)})

    def crawl_url_sync(self, url: str) -> CrawlResult:
        """Synchronous wrapper for crawl_url."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, self.crawl_url(url)).result()
            return loop.run_until_complete(self.crawl_url(url))
        except RuntimeError:
            return asyncio.run(self.crawl_url(url))


# Global default instance
default_crawl4ai_adapter = Crawl4AIAdapter()

