from typing import Any, Dict, Optional
from ..core.interfaces import BaseKnowledgeMemoryBridge
from ..core.models import Note, Notebook


class KnowledgeMemoryBridge(BaseKnowledgeMemoryBridge):
    """Bridges personal knowledge base notes and grounded notebooks with the Unified Memory Layer."""

    def __init__(self, memory_engine: Optional[Any] = None):
        self._memory_engine = memory_engine

    def _get_engine(self, engine_override: Optional[Any] = None) -> Any:
        engine = engine_override or self._memory_engine
        if engine is None:
            # Lazy import from memory package if not injected
            try:
                from memory.engine import MemoryEngine
                engine = MemoryEngine()
                self._memory_engine = engine
            except Exception as e:
                raise RuntimeError(f"MemoryEngine not available for knowledge bridge: {e}")
        return engine

    def ingest_note_to_memory(
        self, note: Note, user_id: str, engine_override: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Ingest a note into the memory engine, extracting facts and archival vectors with note provenance."""
        engine = self._get_engine(engine_override)
        metadata = {
            "source_type": "note",
            "note_id": str(note.id),
            "note_title": note.title,
            "tags": note.tags,
            **note.metadata,
        }

        # Remember note content in the target user and project scope
        result = engine.remember(
            user_id=user_id,
            text=f"# {note.title}\n{note.content}",
            project_id=note.project_id,
            metadata=metadata,
        )

        return {
            "note_id": str(note.id),
            "user_id": user_id,
            "project_id": note.project_id,
            "event_id": result.get("event_id"),
            "facts_saved": result.get("facts_saved", []),
            "archival_record_id": result.get("archival_record_id"),
        }

    def ingest_notebook_to_memory(
        self,
        notebook: Notebook,
        user_id: str,
        engine_override: Optional[Any] = None,
        notebook_engine: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Ingest notebook syntheses and citations into the memory engine."""
        engine = self._get_engine(engine_override)
        
        # Build composite text
        chunks = [f"# Notebook: {notebook.title}"]
        if notebook.description:
            chunks.append(notebook.description)

        for cell in notebook.cells:
            if cell.output:
                chunks.append(f"Grounded Insight: {cell.output}")
            elif cell.content:
                chunks.append(cell.content)

        composite_text = "\n\n".join(chunks)
        metadata = {
            "source_type": "notebook",
            "notebook_id": str(notebook.id),
            "notebook_title": notebook.title,
            "tags": notebook.tags,
        }

        result = engine.remember(
            user_id=user_id,
            text=composite_text,
            project_id=notebook.project_id,
            metadata=metadata,
        )

        return {
            "notebook_id": str(notebook.id),
            "user_id": user_id,
            "project_id": notebook.project_id,
            "event_id": result.get("event_id"),
            "facts_saved": result.get("facts_saved", []),
            "archival_record_id": result.get("archival_record_id"),
        }
