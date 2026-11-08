"""Abstract Base Classes for Global Hybrid Search."""

from abc import ABC, abstractmethod
from typing import List, Tuple
from .models import SearchDocument, SearchQuery, SearchResponse, SearchResult


class BaseSearchEngine(ABC):
    """Abstract interface for hybrid search engines."""

    @abstractmethod
    def index_document(self, doc: SearchDocument) -> None:
        """Upsert a single search document into lexical and vector indices."""
        pass

    @abstractmethod
    def index_batch(self, docs: List[SearchDocument]) -> int:
        """Upsert a batch of search documents."""
        pass

    @abstractmethod
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document by its composite ID."""
        pass

    @abstractmethod
    def delete_by_project(self, project_id: str) -> int:
        """Purge all indexed documents belonging to a project."""
        pass

    @abstractmethod
    def search(self, query: SearchQuery) -> SearchResponse:
        """Execute hybrid search combining BM25 and vector retrieval."""
        pass


class BaseRankFusion(ABC):
    """Abstract contract for rank fusion algorithms (RRF, Borda count, etc.)."""

    @abstractmethod
    def fuse(
        self,
        lexical_hits: List[Tuple[SearchDocument, float]],
        vector_hits: List[Tuple[SearchDocument, float]],
        k: int = 60,
        alpha: float = 0.5,
        limit: int = 20,
    ) -> List[SearchResult]:
        """Combine ordered candidate lists into a fused ranked list."""
        pass
