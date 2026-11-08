"""Unit tests for the Knowledge-to-Memory Bridge: note & notebook memory ingestion."""

from typing import Any, Dict, List, Optional
from uuid import uuid4
import pytest

from knowledge.core.models import Note, Notebook, NotebookCell, CellType
from knowledge.bridge.memory_sync import KnowledgeMemoryBridge


class MockMemoryEngine:
    """Mock MemoryEngine validating memory contract without cross-package namespace collision."""

    def __init__(self):
        self.recorded_events: List[Dict[str, Any]] = []
        self.active_facts: List[Dict[str, Any]] = []

    def remember(
        self,
        user_id: str,
        text: str,
        project_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        event_id = str(uuid4())
        record = {
            "event_id": event_id,
            "user_id": user_id,
            "project_id": project_id,
            "text": text,
            "metadata": metadata or {},
        }
        self.recorded_events.append(record)

        # Extract pseudo facts if found
        saved_facts = []
        if "Python" in text:
            saved_facts.append({"key": "preferred_language", "value": "Python"})
            self.active_facts.append({"key": "preferred_language", "value": "Python", "project_id": project_id})

        return {
            "event_id": event_id,
            "user_id": user_id,
            "project_id": project_id,
            "facts_saved": saved_facts,
            "archival_record_id": str(uuid4()),
        }

    def recall(self, user_id: str, query: str, project_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        matching = [e for e in self.recorded_events if e["user_id"] == user_id]
        if project_id:
            matching = [e for e in matching if e["project_id"] == project_id]
        return {
            "total_tokens": sum(len(e["text"]) // 4 for e in matching),
            "context_str": "\n".join(e["text"] for e in matching),
            "facts": [f for f in self.active_facts if project_id is None or f["project_id"] == project_id],
        }

    def get_active_facts(self, user_id: str, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return [f for f in self.active_facts if project_id is None or f["project_id"] == project_id]


@pytest.fixture
def mock_memory_engine():
    return MockMemoryEngine()


def test_note_ingestion_into_memory(mock_memory_engine):
    bridge = KnowledgeMemoryBridge(memory_engine=mock_memory_engine)
    user = "alice"
    proj = "proj_knowledge"

    note = Note(
        title="Team Coding Standards",
        content="My favorite language is Python and I prefer dark mode.",
        project_id=proj,
        tags=["guidelines", "dev"],
    )

    res = bridge.ingest_note_to_memory(note=note, user_id=user)
    assert res["note_id"] == str(note.id)
    assert res["user_id"] == user
    assert res["project_id"] == proj
    assert res["event_id"] is not None

    # Check recorded event metadata in mock engine
    assert len(mock_memory_engine.recorded_events) == 1
    event = mock_memory_engine.recorded_events[0]
    assert event["project_id"] == proj
    assert event["metadata"]["source_type"] == "note"
    assert event["metadata"]["note_id"] == str(note.id)
    assert event["metadata"]["note_title"] == "Team Coding Standards"
    assert "guidelines" in event["metadata"]["tags"]

    # Verify context recall
    ctx = mock_memory_engine.recall(
        user_id=user,
        query="coding standards language preference",
        project_id=proj,
    )
    assert ctx["total_tokens"] > 0
    assert "Python" in ctx["context_str"]


def test_notebook_ingestion_into_memory(mock_memory_engine):
    bridge = KnowledgeMemoryBridge(memory_engine=mock_memory_engine)
    user = "bob"
    proj = "proj_research"

    nb = Notebook(
        title="Quantum Error Correction",
        description="Topological surface codes analysis",
        project_id=proj,
        cells=[
            NotebookCell(
                cell_type=CellType.MARKDOWN,
                content="Surface codes exhibit a fault-tolerance threshold near 1 percent.",
            ),
            NotebookCell(
                cell_type=CellType.SYNTHESIS,
                content="Synthesis query",
                output="Key finding: Physical qubit overhead scales quadratically with distance.",
            ),
        ],
    )

    res = bridge.ingest_notebook_to_memory(notebook=nb, user_id=user)
    assert res["notebook_id"] == str(nb.id)
    assert res["user_id"] == user
    assert res["project_id"] == proj

    # Check recorded event in engine
    assert len(mock_memory_engine.recorded_events) == 1
    event = mock_memory_engine.recorded_events[0]
    assert event["metadata"]["source_type"] == "notebook"
    assert event["metadata"]["notebook_id"] == str(nb.id)
    assert "Physical qubit overhead" in event["text"]

    # Recall in engine
    ctx = mock_memory_engine.recall(
        user_id=user,
        query="fault-tolerance threshold",
        project_id=proj,
    )
    assert ctx["total_tokens"] > 0
    assert "Quantum Error Correction" in ctx["context_str"]
