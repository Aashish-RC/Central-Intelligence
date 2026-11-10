"""Document and Web Perception modules (Crawl4AI, Unstructured, parsers)."""

from cognitive.perception.document.crawl4ai_adapter import (
    Crawl4AIAdapter,
    CrawlResult,
    default_crawl4ai_adapter,
)
from cognitive.perception.document.unstructured_adapter import (
    DocumentElement,
    ParsedDocument,
    UnstructuredAdapter,
    default_unstructured_adapter,
)

__all__ = [
    "Crawl4AIAdapter",
    "CrawlResult",
    "default_crawl4ai_adapter",
    "DocumentElement",
    "ParsedDocument",
    "UnstructuredAdapter",
    "default_unstructured_adapter",
]
