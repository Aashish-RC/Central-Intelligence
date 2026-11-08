"""Pheonix Global Hybrid Search Engine."""

from .core.models import (
    CorpusType,
    SearchDocument,
    SearchQuery,
    SearchResult,
    SearchResponse,
)
from .engines.local_hybrid import LocalHybridSearchEngine
from .engines.rrf import ReciprocalRankFusion
from .indexer.corpus_indexer import CorpusIndexer
from .core.index import MeilisearchClient, query
from .core.ingestion import (
    SearchIngestionCoordinator,
    ingest_conversation_turn,
    subscribe_to_memory_writes,
)

__all__ = [
    "CorpusType",
    "SearchDocument",
    "SearchQuery",
    "SearchResult",
    "SearchResponse",
    "LocalHybridSearchEngine",
    "ReciprocalRankFusion",
    "CorpusIndexer",
    "MeilisearchClient",
    "query",
    "SearchIngestionCoordinator",
    "ingest_conversation_turn",
    "subscribe_to_memory_writes",
]
