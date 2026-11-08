"""DuckDuckGo Search Provider with offline fallback."""

from typing import List
from urllib.parse import urlparse
from ..core.interfaces import BaseWebSearchProvider
from ..core.models import WebSearchResultItem
from .mock_provider import MockWebSearchProvider


class DuckDuckGoSearchProvider(BaseWebSearchProvider):
    """DuckDuckGo web search provider with automatic fallback to local offline fixture."""

    def __init__(self, fallback_provider: BaseWebSearchProvider = None):
        self._fallback = fallback_provider or MockWebSearchProvider()

    def search(self, query: str, num_results: int = 5) -> List[WebSearchResultItem]:
        # Transparently use fallback provider if live network is unavailable or blocked
        try:
            import urllib.request
            import urllib.parse
            import json

            encoded = urllib.parse.quote_plus(query)
            url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
            req = urllib.request.Request(url, headers={"User-Agent": "Pheonix-Agent/0.1.0"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results: List[WebSearchResultItem] = []
                # Check Abstract
                if data.get("AbstractText") and data.get("AbstractURL"):
                    u = data["AbstractURL"]
                    domain = urlparse(u).netloc or "duckduckgo.com"
                    results.append(
                        WebSearchResultItem(
                            title=data.get("Heading") or query,
                            url=u,
                            snippet=data["AbstractText"],
                            domain=domain,
                        )
                    )
                # Check RelatedTopics
                for topic in data.get("RelatedTopics", []):
                    if isinstance(topic, dict) and topic.get("FirstURL") and topic.get("Text"):
                        u = topic["FirstURL"]
                        domain = urlparse(u).netloc
                        results.append(
                            WebSearchResultItem(
                                title=topic.get("Text")[:60],
                                url=u,
                                snippet=topic["Text"],
                                domain=domain,
                            )
                        )
                        if len(results) >= num_results:
                            break
                if results:
                    return results[:num_results]
        except Exception:
            pass

        return self._fallback.search(query, num_results=num_results)
