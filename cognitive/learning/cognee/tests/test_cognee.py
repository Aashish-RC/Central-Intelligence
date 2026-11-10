"""Unit tests for Cognee Graph-Native Memory Adapter (Task 7.1)."""

import pytest
from cognitive.learning.cognee.cognee_adapter import (
    CogneeAdapter,
    CogneeNode,
    CogneeKnowledgeGraph,
)


def test_can_ingest_a_conversation_and_build_a_knowledge_graph():
    adapter = CogneeAdapter()

    conversation = (
        "User: We are implementing Layer 6 and Layer 7 using TypeScript and Python. "
        "We decided to use TipTap for rich text editing and Cognee for graph memory."
    )

    mem_id = adapter.remember(conversation, user_id="alice")
    assert mem_id.startswith("mem_")

    graph = adapter.get_graph()

    # Verify user and extracted entities exist in knowledge graph
    assert "user_alice" in graph.nodes
    assert any("tiptap" in k for k in graph.nodes.keys())
    assert any("cognee" in k for k in graph.nodes.keys())
    assert any("python" in k for k in graph.nodes.keys())
    assert any("typescript" in k for k in graph.nodes.keys())

    # Verify relationships were constructed
    assert len(graph.edges) > 0
    tiptap_node = next(n for n in graph.nodes.values() if n.name == "Tiptap")
    assert tiptap_node.node_type == "framework"


def test_cognee_remember_recall_improve_forget():
    adapter = CogneeAdapter()

    adapter.remember("Deploying PostgreSQL database for vector indexing", user_id="admin")

    # Recall
    recalled = adapter.recall("PostgreSQL")
    assert len(recalled) > 0
    node = recalled[0]
    assert node.name == "Postgresql"

    # Improve
    improved = adapter.improve(node.id, {"version": "16.1", "cluster_size": 3})
    assert improved is True
    assert adapter.graph.nodes[node.id].attributes["version"] == "16.1"

    # Forget
    forgotten = adapter.forget(node.id)
    assert forgotten is True
    assert node.id not in adapter.graph.nodes
    assert not any(e.source_id == node.id or e.target_id == node.id for e in adapter.graph.edges)

