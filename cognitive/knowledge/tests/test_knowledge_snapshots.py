"""Unit and integration tests for Point-in-Time Knowledge Snapshots (Feature 3.24)."""

import pytest
from knowledge.snapshots import (
    GraphRelationshipSnapshot,
    KnowledgeItemSnapshot,
    KnowledgeSnapshotManager,
)


def test_create_and_retrieve_knowledge_snapshot():
    mgr = KnowledgeSnapshotManager()
    items = [
        KnowledgeItemSnapshot(
            id="doc-1",
            title="System Architecture Guide",
            content="Micro-architectures connect services via gRPC and event buses.",
            tags=["architecture", "backend"],
            version=1,
            created_at="2026-01-01T00:00:00Z",
        ),
        KnowledgeItemSnapshot(
            id="doc-2",
            title="Database Schema",
            content="PostgreSQL schema for user accounts and organizations.",
            tags=["database", "schema"],
            version=1,
            created_at="2026-01-01T00:00:00Z",
        ),
    ]
    rels = [
        GraphRelationshipSnapshot(source="doc-1", relation="REFERENCES", target="doc-2"),
    ]

    snap = mgr.create_snapshot(
        items=items,
        relationships=rels,
        tag="v1.0-release",
        description="Q1 Architecture snapshot",
    )

    assert snap.snapshot_id.startswith("ksnap_")
    assert snap.tag == "v1.0-release"
    assert snap.total_items == 2
    assert snap.total_relationships == 1

    retrieved = mgr.get_snapshot(snap.snapshot_id)
    assert retrieved is not None
    assert retrieved.snapshot_id == snap.snapshot_id
    assert len(retrieved.items) == 2


def test_diff_snapshots_detects_additions_removals_modifications():
    mgr = KnowledgeSnapshotManager()

    # Base snapshot
    item_a = KnowledgeItemSnapshot(id="doc-a", title="Doc A", content="Original content A", version=1, created_at="2026-01-01T00:00:00Z")
    item_b = KnowledgeItemSnapshot(id="doc-b", title="Doc B", content="Original content B", version=1, created_at="2026-01-01T00:00:00Z")
    snap_v1 = mgr.create_snapshot(items=[item_a, item_b], tag="v1")

    # Target snapshot: item_a modified, item_b removed, item_c added
    item_a_mod = KnowledgeItemSnapshot(id="doc-a", title="Doc A", content="Updated content A", version=2, created_at="2026-02-01T00:00:00Z")
    item_c = KnowledgeItemSnapshot(id="doc-c", title="Doc C", content="New content C", version=1, created_at="2026-02-01T00:00:00Z")
    rel_new = GraphRelationshipSnapshot(source="doc-a", relation="LINKS_TO", target="doc-c")
    snap_v2 = mgr.create_snapshot(items=[item_a_mod, item_c], relationships=[rel_new], tag="v2")

    diff = mgr.diff_snapshots(snap_v1.snapshot_id, snap_v2.snapshot_id)

    assert len(diff.added_items) == 1
    assert diff.added_items[0].id == "doc-c"

    assert len(diff.removed_items) == 1
    assert diff.removed_items[0].id == "doc-b"

    assert len(diff.modified_items) == 1
    assert diff.modified_items[0]["id"] == "doc-a"
    assert diff.modified_items[0]["new_version"] == 2

    assert len(diff.added_relationships) == 1
    assert diff.added_relationships[0].relation == "LINKS_TO"


def test_query_point_in_time():
    mgr = KnowledgeSnapshotManager()
    items = [
        KnowledgeItemSnapshot(id="k1", title="Quantum Computing", content="Qubits and superposition.", tags=["physics"], version=1, created_at="2026-01-01T00:00:00Z"),
        KnowledgeItemSnapshot(id="k2", title="Classical Computing", content="Bits and boolean logic gates.", tags=["electronics"], version=1, created_at="2026-01-01T00:00:00Z"),
    ]
    snap = mgr.create_snapshot(items=items, tag="physics-v1")

    # Query for quantum
    results = mgr.query_point_in_time(snap.snapshot_id, "qubit")
    assert len(results) == 1
    assert results[0].id == "k1"

    # Query matching tag
    results_tag = mgr.query_point_in_time(snap.snapshot_id, "electronics")
    assert len(results_tag) == 1
    assert results_tag[0].id == "k2"

    # Query non-existent
    results_empty = mgr.query_point_in_time(snap.snapshot_id, "astronomy")
    assert len(results_empty) == 0
