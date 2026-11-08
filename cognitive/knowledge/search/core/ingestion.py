"""Real-Time Ingestion and Event Subscription for Global Search."""

from typing import Any, Callable, Dict, List, Optional
from .index import get_default_client, MeilisearchClient
from .models import CorpusType, SearchDocument, utc_now


class SearchIngestionCoordinator:
    """Coordinates real-time ingestion from memory, conversations, notes, and artifacts."""

    def __init__(self, client: Optional[MeilisearchClient] = None):
        self.client = client or get_default_client()

    def ingest_conversation_turn(
        self,
        session_id: str,
        message_id: str,
        role: str,
        text: str,
        project_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SearchDocument:
        """Indexes a conversational turn into the conversations index."""
        doc = SearchDocument(
            id=f"conv:{session_id}:{message_id}",
            corpus_type=CorpusType.CONVERSATION,
            project_id=project_id,
            title=f"Conversation Turn ({role}) in {session_id[:8]}",
            content=text,
            tags=["conversation", role.lower(), session_id],
            metadata={
                "session_id": session_id,
                "message_id": message_id,
                "role": role,
                **(metadata or {}),
            },
            timestamp=utc_now(),
        )
        self.client.index_document(doc)
        return doc

    def ingest_note(
        self,
        note_id: str,
        title: str,
        content: str,
        project_id: str = "default",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SearchDocument:
        """Indexes a note into the notes index."""
        doc = SearchDocument(
            id=f"note:{note_id}",
            corpus_type=CorpusType.NOTE,
            project_id=project_id,
            title=title,
            content=content,
            tags=["note"] + (tags or []),
            metadata={
                "note_id": note_id,
                **(metadata or {}),
            },
            timestamp=utc_now(),
        )
        self.client.index_document(doc)
        return doc

    def ingest_artifact(
        self,
        artifact_id: str,
        title: str,
        content: str,
        project_id: str = "default",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SearchDocument:
        """Indexes an artifact or file into the artifacts index."""
        doc = SearchDocument(
            id=f"artifact:{artifact_id}",
            corpus_type=CorpusType.ARTIFACT,
            project_id=project_id,
            title=title,
            content=content,
            tags=["artifact"] + (tags or []),
            metadata={
                "artifact_id": artifact_id,
                **(metadata or {}),
            },
            timestamp=utc_now(),
        )
        self.client.index_document(doc)
        return doc

    def subscribe_to_memory_writes(self, memory_engine: Any) -> Callable:
        """Subscribes to memory engine write events to automatically ingest memory into search."""
        original_remember = getattr(memory_engine, "remember", None)
        if original_remember is None:
            return lambda: None

        def hooked_remember(user_id: str, text: str, *args, **kwargs):
            result = original_remember(user_id, text, *args, **kwargs)
            try:
                # Ingest into search index
                self.ingest_conversation_turn(
                    session_id=f"mem_{user_id}",
                    message_id=str(getattr(result, "id", hash(text))),
                    role="user",
                    text=text,
                    metadata={"source": "memory_engine", "user_id": user_id},
                )
            except Exception:
                pass
            return result

        memory_engine.remember = hooked_remember

        def unsubscribe():
            memory_engine.remember = original_remember

        return unsubscribe


_global_coordinator: Optional[SearchIngestionCoordinator] = None


def get_default_coordinator() -> SearchIngestionCoordinator:
    global _global_coordinator
    if _global_coordinator is None:
        _global_coordinator = SearchIngestionCoordinator()
    return _global_coordinator


def ingest_conversation_turn(
    session_id: str,
    message_id: str,
    role: str,
    text: str,
    project_id: str = "default",
    metadata: Optional[Dict[str, Any]] = None,
) -> SearchDocument:
    return get_default_coordinator().ingest_conversation_turn(
        session_id=session_id,
        message_id=message_id,
        role=role,
        text=text,
        project_id=project_id,
        metadata=metadata,
    )


def subscribe_to_memory_writes(memory_engine: Any) -> Callable:
    return get_default_coordinator().subscribe_to_memory_writes(memory_engine)


__all__ = [
    "SearchIngestionCoordinator",
    "get_default_coordinator",
    "ingest_conversation_turn",
    "subscribe_to_memory_writes",
]
