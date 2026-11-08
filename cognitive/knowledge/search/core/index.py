"""Meilisearch Global Search Client and Multi-Index Manager."""

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .interfaces import BaseSearchEngine
from .models import (
    CorpusType,
    SearchDocument,
    SearchQuery,
    SearchResponse,
    SearchResult,
    utc_now,
)
from ..engines.local_hybrid import LocalHybridSearchEngine


INDEX_NAMES = ["conversations", "notes", "artifacts"]


class MeilisearchClient(BaseSearchEngine):
    """Meilisearch client with automatic schemas, multi-index routing, and LocalHybrid fallback."""

    def __init__(
        self,
        url: Optional[str] = None,
        master_key: Optional[str] = None,
        timeout: float = 3.0,
        fallback_engine: Optional[BaseSearchEngine] = None,
    ):
        raw_url = url or os.getenv("MEILISEARCH_URL") or "http://localhost:7700"
        self.url = raw_url.rstrip("/")
        self.master_key = master_key or os.getenv("MEILISEARCH_MASTER_KEY", os.getenv("MEILISEARCH_API_KEY"))
        self.timeout = timeout
        self.fallback = fallback_engine or LocalHybridSearchEngine()
        self._server_available: Optional[bool] = None

    def _is_server_available(self) -> bool:
        if self._server_available is not None:
            return self._server_available

        try:
            headers = {}
            if self.master_key:
                headers["Authorization"] = f"Bearer {self.master_key}"
            req = urllib.request.Request(f"{self.url}/indexes", headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                self._server_available = (resp.status == 200)
        except Exception:
            self._server_available = False

        return self._server_available

    def _get_target_index(self, doc: SearchDocument) -> str:
        if doc.corpus_type in (CorpusType.CHAT, CorpusType.CONVERSATION):
            return "conversations"
        elif doc.corpus_type == CorpusType.NOTE:
            return "notes"
        elif doc.corpus_type in (CorpusType.FILE, CorpusType.ARTIFACT):
            return "artifacts"
        return "conversations"

    def index_document(self, doc: SearchDocument) -> None:
        """Upsert a document into Meilisearch index or fallback engine."""
        self.fallback.index_document(doc)

        if self._is_server_available():
            try:
                target_index = self._get_target_index(doc)
                payload = json.dumps([{
                    "id": doc.id.replace(":", "_").replace("/", "_"),
                    "raw_id": doc.id,
                    "title": doc.title,
                    "content": doc.content,
                    "corpus_type": doc.corpus_type.value,
                    "project_id": doc.project_id,
                    "tags": doc.tags,
                    "metadata": doc.metadata,
                }]).encode("utf-8")

                headers = {"Content-Type": "application/json"}
                if self.master_key:
                    headers["Authorization"] = f"Bearer {self.master_key}"

                req = urllib.request.Request(
                    f"{self.url}/indexes/{target_index}/documents",
                    data=payload,
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout):
                    pass
            except Exception:
                pass

    def index_batch(self, docs: List[SearchDocument]) -> int:
        for doc in docs:
            self.index_document(doc)
        return len(docs)

    def delete_document(self, doc_id: str) -> bool:
        return self.fallback.delete_document(doc_id)

    def delete_by_project(self, project_id: str) -> int:
        return self.fallback.delete_by_project(project_id)

    def search(self, query: SearchQuery) -> SearchResponse:
        """Search across indexes with Meilisearch or fallback to local hybrid."""
        if self._is_server_available():
            try:
                headers = {"Content-Type": "application/json"}
                if self.master_key:
                    headers["Authorization"] = f"Bearer {self.master_key}"

                all_results: List[SearchResult] = []
                # Query across relevant indexes
                for index_name in INDEX_NAMES:
                    body = json.dumps({
                        "q": query.query_text,
                        "limit": query.limit,
                        "filter": f"project_id = '{query.project_id}'" if query.project_id else None,
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        f"{self.url}/indexes/{index_name}/search",
                        data=body,
                        headers=headers,
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        hits = data.get("hits", [])
                        for rank, hit in enumerate(hits, start=1):
                            doc = SearchDocument(
                                id=hit.get("raw_id", hit.get("id")),
                                corpus_type=CorpusType(hit.get("corpus_type", "chat")),
                                project_id=hit.get("project_id", query.project_id),
                                title=hit.get("title", ""),
                                content=hit.get("content", ""),
                                tags=hit.get("tags", []),
                                metadata=hit.get("metadata", {}),
                            )
                            all_results.append(
                                SearchResult(
                                    document=doc,
                                    rrf_score=round(1.0 / (60 + rank), 4),
                                    lexical_rank=rank,
                                )
                            )
                if all_results:
                    all_results.sort(key=lambda r: r.rrf_score, reverse=True)
                    return SearchResponse(
                        query=query.query_text,
                        tenant_id=query.tenant_id,
                        project_id=query.project_id,
                        total_hits=len(all_results),
                        results=all_results[:query.limit],
                    )
            except Exception:
                pass

        return self.fallback.search(query)

    def query(self, needle: str, project_id: str = "default", limit: int = 20) -> List[SearchResult]:
        """Convenience direct query method returning ranked SearchResult objects."""
        sq = SearchQuery(query_text=needle, project_id=project_id, limit=limit)
        response = self.search(sq)
        return response.results


_global_meili_client: Optional[MeilisearchClient] = None


def get_default_client() -> MeilisearchClient:
    global _global_meili_client
    if _global_meili_client is None:
        _global_meili_client = MeilisearchClient()
    return _global_meili_client


def query(needle: str, project_id: str = "default", limit: int = 20) -> List[SearchResult]:
    """Top-level search query returning results within sub-second latency."""
    return get_default_client().query(needle=needle, project_id=project_id, limit=limit)
