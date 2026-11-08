"""Offline deterministic mock web search provider for hermetic testing."""

import re
from typing import List
from urllib.parse import urlparse
from ..core.interfaces import BaseWebSearchProvider
from ..core.models import WebSearchResultItem


FIXTURE_CORPUS = [
    WebSearchResultItem(
        title="Python 3.14 Release Notes and Documentation",
        url="https://docs.python.org/3/whatsnew/3.14.html",
        snippet="Python 3.14 includes template strings, performance enhancements, and improved garbage collection.",
        domain="docs.python.org",
        published_date="2026-10-01",
    ),
    WebSearchResultItem(
        title="AES-256-GCM Cryptographic Standard and Best Practices",
        url="https://csrc.nist.gov/publications/detail/sp/800-38d/final",
        snippet="NIST SP 800-38D specifies Galois/Counter Mode (GCM) for authenticated encryption with AES-256.",
        domain="csrc.nist.gov",
        published_date="2026-04-15",
    ),
    WebSearchResultItem(
        title="Raft Distributed Consensus Algorithm Specification",
        url="https://raft.github.io/raft.pdf",
        snippet="Raft is a consensus algorithm designed for understandable replicated state machine management.",
        domain="raft.github.io",
        published_date="2026-05-20",
    ),
    WebSearchResultItem(
        title="FastAPI Web Framework High-Performance Guide",
        url="https://fastapi.tiangolo.com/benchmarks/",
        snippet="FastAPI is a modern web framework for building APIs with Python based on standard type hints.",
        domain="fastapi.tiangolo.com",
        published_date="2026-08-11",
    ),
]


class MockWebSearchProvider(BaseWebSearchProvider):
    """Deterministic offline search fixture returning keyword-ranked web results."""

    def __init__(self, custom_corpus: List[WebSearchResultItem] = None):
        self._corpus = custom_corpus or FIXTURE_CORPUS

    def search(self, query: str, num_results: int = 5) -> List[WebSearchResultItem]:
        tokens = re.findall(r"\w+", query.lower())
        if not tokens:
            return self._corpus[:num_results]

        scored: list = []
        for item in self._corpus:
            text = f"{item.title} {item.snippet}".lower()
            score = sum(1 for t in tokens if t in text)
            if score > 0:
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [item for _, item in scored]
        if not results:
            results = self._corpus
        return results[:num_results]
