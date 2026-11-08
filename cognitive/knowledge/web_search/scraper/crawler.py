"""Polite Web Crawler with user-agent, rate limiting, and HTML parsing."""

import time
from typing import Optional
import urllib.request

from ..core.interfaces import BaseWebScraper
from ..core.models import ScrapedPage
from .parser import HTMLMarkdownParser


class PoliteCrawler(BaseWebScraper):
    """Polite HTTP scraper with custom User-Agent, timeouts, and clean markdown extraction."""

    def __init__(
        self,
        user_agent: str = "PheonixResearchBot/1.0 (+https://github.com/Aashish-RC/pheonix)",
        timeout_seconds: float = 5.0,
        rate_limit_delay: float = 0.1,
    ):
        self._user_agent = user_agent
        self._timeout = timeout_seconds
        self._delay = rate_limit_delay
        self._last_fetch_time: float = 0.0

    def scrape(self, url: str, html_override: Optional[str] = None) -> ScrapedPage:
        """Fetch URL (or parse provided HTML override) and convert to clean markdown."""
        if html_override is not None:
            return HTMLMarkdownParser.parse_html(html_override, url=url)

        # Rate limiting delay
        elapsed = time.time() - self._last_fetch_time
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)

        headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw_bytes = resp.read()
                raw_html = raw_bytes.decode("utf-8", errors="replace")
                self._last_fetch_time = time.time()
                return HTMLMarkdownParser.parse_html(raw_html, url=url)
        except Exception as e:
            # Fallback empty page on network errors
            raw_html = f"<html><body><h1>Error</h1><p>Failed to retrieve {url}: {e}</p></body></html>"
            return HTMLMarkdownParser.parse_html(raw_html, url=url)
