"""DuckDuckGo Search Provider with offline fallback."""

import logging
from typing import List, Optional
from urllib.parse import urlparse

from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    is_production,
    require_live_adapter,
)
from ..core.interfaces import BaseWebSearchProvider
from ..core.models import WebSearchResultItem
from .mock_provider import MockWebSearchProvider

logger = logging.getLogger("cognitive.knowledge.web_search.duckduckgo")


class DuckDuckGoSearchProvider(BaseWebSearchProvider):
    """DuckDuckGo web search provider with automatic fallback to local offline fixture in dev."""

    def __init__(self, fallback_provider: Optional[BaseWebSearchProvider] = None):
        self.adapter_mode = require_live_adapter("duckduckgo")
        if is_production():
            if isinstance(fallback_provider, MockWebSearchProvider):
                raise ProductionSafetyError(
                    "DuckDuckGo provider cannot use MockWebSearchProvider in production."
                )
            self._fallback = fallback_provider
        else:
            self._fallback = fallback_provider or MockWebSearchProvider()

    def search(self, query: str, num_results: int = 5) -> List[WebSearchResultItem]:
        self.adapter_mode = require_live_adapter("duckduckgo")
        # Transparently use fallback provider only when not in production / live mode
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
                fail_closed_in_production(
                    "duckduckgo",
                    f"DuckDuckGo live search returned no results for '{query}'",
                )
        except ProductionSafetyError:
            raise
        except Exception as exc:
            fail_closed_in_production(
                "duckduckgo",
                f"DuckDuckGo live search failed: {exc}",
                cause=exc,
            )
            logger.debug("DuckDuckGo live search unavailable, using fallback: %s", exc)

        if self._fallback is None:
            raise ProductionSafetyError("DuckDuckGo search failed and no live fallback is configured.")
        return self._fallback.search(query, num_results=num_results)
