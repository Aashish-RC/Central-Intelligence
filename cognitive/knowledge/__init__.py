"""Pheonix Knowledge and Docs Engine."""

from .core.models import (
    Note,
    Notebook,
    NotebookCell,
    CellType,
    CitationAnchor,
    BacklinkRef,
)
from .notes.store import NoteStore
from .notes.parser import NoteParser
from .notes.graph import KnowledgeGraph
from .notebooks.engine import NotebookEngine
from .bridge.memory_sync import KnowledgeMemoryBridge
from typing import Any, Optional, List


def index_document(
    file_id: str,
    content: Any,
    filename: str,
    project_id: str = "default",
    tags: Optional[List[str]] = None,
    metadata: Optional[dict] = None,
    store: Optional[NoteStore] = None,
) -> Note:
    """Helper to directly index a storage document into knowledge base."""
    target_store = store or NoteStore()
    return target_store.index_document(
        file_id=file_id,
        content=content,
        filename=filename,
        project_id=project_id,
        tags=tags,
        metadata=metadata,
    )


__all__ = [
    "Note",
    "Notebook",
    "NotebookCell",
    "CellType",
    "CitationAnchor",
    "BacklinkRef",
    "NoteStore",
    "NoteParser",
    "KnowledgeGraph",
    "NotebookEngine",
    "KnowledgeMemoryBridge",
    "index_document",
]
