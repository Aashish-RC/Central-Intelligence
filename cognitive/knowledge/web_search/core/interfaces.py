"""Abstract interfaces for Web Search, Scraping, and Verification."""

from abc import ABC, abstractmethod
from typing import List, Optional
from .models import ScrapedPage, SourceSupportCheck, WebSearchResultItem


class BaseWebSearchProvider(ABC):
    """Abstract provider adapter for web search queries."""

    @abstractmethod
    def search(self, query: str, num_results: int = 5) -> List[WebSearchResultItem]:
        """Execute web query and return normalized results."""
        pass


class BaseWebScraper(ABC):
    """Abstract scraper for fetching and converting web pages into clean markdown."""

    @abstractmethod
    def scrape(self, url: str, html_override: Optional[str] = None) -> ScrapedPage:
        """Fetch URL (or parse html_override) and extract structured content."""
        pass


class BaseSourceVerifier(ABC):
    """Abstract verifier for hallucination checking and citation grounding."""

    @abstractmethod
    def verify_claim(
        self,
        claim: str,
        source: ScrapedPage,
        threshold: float = 0.65,
    ) -> SourceSupportCheck:
        """Evaluate if the given claim is supported by the scraped source text."""
        pass
