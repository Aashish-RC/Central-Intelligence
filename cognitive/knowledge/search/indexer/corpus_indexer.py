"""Multi-Corpus Indexer: Synchronizing chats, files, notes, and memory into Global Search."""

from typing import Any, Dict, List, Optional
from ..core.models import (
    CorpusType,
    SearchDocument,
    SearchQuery,
    SearchResponse,
)
from ..engines.local_hybrid import LocalHybridSearchEngine


class CorpusIndexer:
    """Orchestrates indexing and unified retrieval across chats, files, notes, and memory."""

    def __init__(self, engine: Optional[LocalHybridSearchEngine] = None):
        self._engine = engine or LocalHybridSearchEngine()

    @property
    def engine(self) -> LocalHybridSearchEngine:
        return self._engine

    def index_chat_message(
        self,
        message_id: str,
        session_id: str,
        role: str,
        text: str,
        project_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SearchDocument:
        """Index a conversational turn from the agent or user."""
        doc = SearchDocument(
            id=f"chat:{message_id}",
            corpus_type=CorpusType.CHAT,
            project_id=project_id,
            title=f"Chat Turn ({role}) in {session_id[:8]}",
            content=text,
            tags=["chat", role.lower()],
            metadata={
                "message_id": message_id,
                "session_id": session_id,
                "role": role,
                **(metadata or {}),
            },
        )
        self._engine.index_document(doc)
        return doc

    def index_storage_file(
        self,
        file_id: str,
        filename: str,
        content_summary: str,
        sha256: str,
        project_id: str = "default",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SearchDocument:
        """Index a file or blob tracked by the storage layer."""
        all_tags = ["file"] + (tags or [])
        doc = SearchDocument(
            id=f"file:{file_id}",
            corpus_type=CorpusType.FILE,
            project_id=project_id,
            title=filename,
            content=content_summary,
            tags=all_tags,
            metadata={
                "file_id": file_id,
                "filename": filename,
                "sha256": sha256,
                **(metadata or {}),
            },
        )
        self._engine.index_document(doc)
        return doc

    def index_knowledge_note(
        self,
        note_id: str,
        title: str,
        content: str,
        project_id: str = "default",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SearchDocument:
        """Index a personal knowledge note or notebook cell."""
        all_tags = ["note"] + (tags or [])
        doc = SearchDocument(
            id=f"note:{note_id}",
            corpus_type=CorpusType.NOTE,
            project_id=project_id,
            title=title,
            content=content,
            tags=all_tags,
            metadata={
                "note_id": note_id,
                "title": title,
                **(metadata or {}),
            },
        )
        self._engine.index_document(doc)
        return doc

    def index_memory_fact(
        self,
        fact_id: str,
        key: str,
        value: str,
        project_id: str = "default",
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SearchDocument:
        """Index a structured ground-truth fact from the memory engine."""
        doc = SearchDocument(
            id=f"memory:{fact_id}",
            corpus_type=CorpusType.MEMORY,
            project_id=project_id,
            title=f"Fact: {key}",
            content=f"{key}: {value}",
            tags=["memory", category.lower() if category else "fact"],
            metadata={
                "fact_id": fact_id,
                "key": key,
                "value": value,
                "category": category,
                **(metadata or {}),
            },
        )
        self._engine.index_document(doc)
        return doc

    def search(
        self,
        query_text: str,
        project_id: str = "default",
        corpus_types: Optional[List[CorpusType]] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
        hybrid_alpha: float = 0.5,
    ) -> SearchResponse:
        """Perform unified hybrid cross-corpus search."""
        query = SearchQuery(
            query_text=query_text,
            project_id=project_id,
            corpus_types=corpus_types,
            tags=tags,
            limit=limit,
            hybrid_alpha=hybrid_alpha,
        )
        return self._engine.search(query)
