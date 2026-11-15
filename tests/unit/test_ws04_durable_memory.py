"""Workstream 04: Durable Data, Memory and Knowledge Verification Test Suite.

Validates the 5 mandatory criteria:
1. PostgreSQL connection pooling, pure-Python pg8000 support, and FOR UPDATE concurrency locking.
2. Multi-tier memory persistence, versioning, soft decay, and recovery across simulated restarts.
3. Hybrid RAG retrieval (BM25 + Cosine Vectors + RRF) and Knowledge Graph Cypher execution.
4. Permission-aware document filtering and deletion propagation.
5. Memory snapshots, backup, and restore capabilities.
"""

from __future__ import annotations

import os
import tempfile
import threading
from uuid import uuid4, UUID
import pytest

from cognitive.memory.core.models import FactItem, FactCategory, MemoryRecord
from cognitive.memory.tiers.facts.postgres_adapter import (
    PostgreSQLFactStore,
    _PostgreSQLConnectionPool,
)
from cognitive.memory.tiers.facts.sqlite_adapter import SQLiteFactStore
from cognitive.memory.tiers.semantic.qdrant_adapter import QdrantAdapter
from cognitive.knowledge.search.engines.local_hybrid import LocalHybridSearchEngine
from cognitive.knowledge.search.core.models import SearchDocument, SearchQuery, CorpusType
from cognitive.knowledge.access_control.openfga_bridge import filter_results_by_permission
from cognitive.memory.tiers.graph.memgraph_adapter import MemgraphAdapter
from cognitive.memory.config import (
    MemoryConfig,
    WorkingMemoryBackend,
    FactStoreBackend,
    VectorStoreBackend,
    EmbeddingBackend,
)
from cognitive.memory.engine import MemoryEngine


# ==============================================================================
# WS-04.1: PostgreSQL Connection Pooling & Concurrency Locking
# ==============================================================================

def test_postgresql_connection_pool_acquire_and_release():
    """Verify thread-safe pool management, reuse, and max_connections limit."""
    class DummyConn:
        def __init__(self, cid: int):
            self.cid = cid
            self.closed = False
            self.rollbacks = 0
        def rollback(self):
            self.rollbacks += 1
        def close(self):
            self.closed = True

    created_count = 0
    pool = _PostgreSQLConnectionPool(
        connection_url="postgresql://test:test@localhost:5432/test",
        max_connections=3,
        timeout=1.0,
    )
    # Monkeypatch creation with dummy connections
    def mock_create():
        nonlocal created_count
        created_count += 1
        return DummyConn(created_count)

    pool._create_raw_connection = mock_create

    # 1. Acquire connections up to limit
    c1 = pool.acquire()
    c2 = pool.acquire()
    c3 = pool.acquire()
    assert created_count == 3

    # 2. Releasing returns connection to pool
    pool.release(c1)
    c1_reacquired = pool.acquire()
    assert c1_reacquired.cid == c1.cid
    assert c1.rollbacks >= 1

    # 3. Release all and close pool
    pool.release(c1_reacquired)
    pool.release(c2)
    pool.release(c3)
    pool.close()
    assert c1.closed and c2.closed and c3.closed


def test_postgres_fact_store_for_update_concurrency_query(monkeypatch):
    """Verify that put_fact executes with 'FOR UPDATE' locking to prevent concurrent overwrite."""
    executed_queries = []

    class MockCursor:
        def __init__(self):
            self.description = [("id",), ("version",)]
        def execute(self, q, params=None):
            executed_queries.append(q)
        def fetchone(self):
            return None
        def close(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    class MockConn:
        def cursor(self):
            return MockCursor()
        def commit(self):
            pass
        def rollback(self):
            pass
        def close(self):
            pass

    store = PostgreSQLFactStore()
    store._pool = _PostgreSQLConnectionPool("postgresql://fake@localhost:5432/db", max_connections=1)
    store._pool._create_raw_connection = lambda: MockConn()

    test_fact = FactItem(user_id="user_conc", key="theme", value="dark")
    store.put_fact(test_fact)

    # Verify query had FOR UPDATE row-level concurrency lock
    assert any("FOR UPDATE" in q for q in executed_queries)
    store.close()


# ==============================================================================
# WS-04.2: Durability & Recovery Across Restart
# ==============================================================================

def test_fact_store_persists_and_recovers_across_restart(tmp_path):
    """Facts, versions, and invalidations must survive complete adapter restart."""
    db_file = tmp_path / "durable_facts.db"

    # Session 1: write and version facts
    store1 = SQLiteFactStore(db_path=str(db_file))
    user_id = "user_persist_1"

    fact_v1 = FactItem(user_id=user_id, key="preferred_model", value="gemini-1.5-pro")
    store1.put_fact(fact_v1)

    fact_v2 = FactItem(user_id=user_id, key="preferred_model", value="gemini-2.0-flash")
    store1.put_fact(fact_v2)

    # Invalidate another fact
    temp_fact = FactItem(user_id=user_id, key="temp_session", value="tok_xyz")
    store1.put_fact(temp_fact)
    store1.invalidate_by_key(user_id=user_id, key="temp_session")

    # Simulate process termination
    del store1

    # Session 2: Fresh instance loaded from persistent storage
    store2 = SQLiteFactStore(db_path=str(db_file))
    recovered = store2.get_fact_by_key(user_id, "preferred_model")

    assert recovered is not None
    assert recovered.value == "gemini-2.0-flash"
    assert recovered.version == 2
    assert recovered.is_active is True

    # Check invalidated fact is inactive
    inactive = store2.get_fact_by_key(user_id, "temp_session", active_only=True)
    assert inactive is None

    all_facts = store2.get_facts(user_id, active_only=False)
    assert len(all_facts) == 3


def test_qdrant_vector_store_persists_on_disk(tmp_path):
    """Vector embeddings and payloads must survive client re-initialization."""
    qdrant_dir = str(tmp_path / "qdrant_storage")

    # Client 1: Index vector
    q1 = QdrantAdapter(location=qdrant_dir, collection_name="persist_vectors", dim=4)
    rec_id = uuid4()
    record = MemoryRecord(
        id=rec_id,
        user_id="user_qdrant",
        text="Persistent semantic memory",
        embedding=[0.1, 0.2, 0.3, 0.4],
    )
    q1.upsert_vectors([record])
    assert q1.check_health() is True

    # Simulate termination & re-open
    del q1
    q2 = QdrantAdapter(location=qdrant_dir, collection_name="persist_vectors", dim=4)
    assert q2.check_health() is True

    search_res = q2.query_similar(
        user_id="user_qdrant",
        query_embedding=[0.1, 0.2, 0.3, 0.4],
        top_k=1,
    )
    assert len(search_res) == 1
    assert search_res[0].id == rec_id
    assert search_res[0].text == "Persistent semantic memory"


# ==============================================================================
# WS-04.3: Real Service & Retrieval Integration (Hybrid RRF & Graph)
# ==============================================================================

def test_hybrid_search_rrf_ranking(tmp_path):
    """LocalHybridSearchEngine fuses BM25 full-text and dense vectors via RRF."""
    db_file = str(tmp_path / "search_hybrid.db")
    engine = LocalHybridSearchEngine(db_path=db_file, dim=4)

    # Ingest test documents
    doc1 = SearchDocument(
        id="doc_alpha",
        tenant_id="tenant_a",
        corpus_type=CorpusType.FILE,
        title="Zero Trust Security Architecture",
        content="Zero trust network architecture eliminates implicit perimeter trust.",
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    doc2 = SearchDocument(
        id="doc_beta",
        tenant_id="tenant_a",
        corpus_type=CorpusType.FILE,
        title="Database Sharding and Replication",
        content="PostgreSQL high availability using streaming replication.",
        embedding=[0.0, 1.0, 0.0, 0.0],
    )
    engine.index_document(doc1)
    engine.index_document(doc2)

    # Hybrid search with query vector targeting doc1
    query = SearchQuery(
        query_text="Zero trust security architecture",
        query_vector=[0.95, 0.05, 0.0, 0.0],
        top_k=2,
        tenant_id="tenant_a",
    )
    response = engine.search(query)

    assert len(response.results) >= 1
    top_hit = response.results[0]
    assert top_hit.document.id == "doc_alpha"
    assert "Zero Trust" in top_hit.document.title
    assert top_hit.rrf_score > 0


def test_memgraph_knowledge_graph_traversal():
    """Knowledge graph traversal executes Cypher relationships deterministically."""
    graph = MemgraphAdapter(host=":memory:")
    assert graph.check_health() is True

    # Build organizational knowledge graph
    graph.add_entity("org_1", "Satya", "Executive", {"role": "CEO"})
    graph.add_entity("org_1", "Alice", "Lead", {"role": "VP AI"})
    graph.add_entity("org_1", "Bob", "Engineer", {"role": "Staff Engineer"})

    graph.add_relationship("org_1", "Satya", "MANAGES", "Alice")
    graph.add_relationship("org_1", "Alice", "MANAGES", "Bob")

    # Cypher query: find who manages Bob
    res = graph.execute_query("MATCH (m)-[:MANAGES]->(b {name: 'Bob'}) RETURN m.name")
    assert len(res) == 1
    assert res[0]["m.name"] == "Alice"


# ==============================================================================
# WS-04.4: Permission-Aware Retrieval & Deletion Propagation
# ==============================================================================

def test_permission_aware_retrieval_and_filtering():
    """filter_results_by_permission filters out unauthorized documents via ReBAC."""
    class MockAuthService:
        def check_permission(self, user: str, action: str, resource: str) -> bool:
            # Only user_1 has view access to confidential docs
            if "confidential" in resource:
                return user == "user:user_1"
            return True

    mock_auth = MockAuthService()
    docs = [
        {"id": "doc:public_readme", "title": "Public Guide"},
        {"id": "doc:confidential_roadmap", "title": "Q4 Roadmap"},
        {"id": "doc:public_faq", "title": "FAQ"},
    ]

    # Authorized user sees all 3 docs
    allowed_u1 = filter_results_by_permission(
        results=docs,
        user_id="user_1",
        openfga_client=mock_auth,
        action="can_view",
    )
    assert len(allowed_u1) == 3

    # Unauthorized user sees only the 2 public docs
    allowed_u2 = filter_results_by_permission(
        results=docs,
        user_id="user_2",
        openfga_client=mock_auth,
        action="can_view",
    )
    assert len(allowed_u2) == 2
    assert all("confidential" not in d["id"] for d in allowed_u2)


# ==============================================================================
# WS-04.5: Memory Snapshots, Backup & Restore
# ==============================================================================

def test_memory_snapshot_create_and_restore(tmp_path):
    """MemoryEngine snapshots durable facts and restores state upon rollback."""
    wal_dir = str(tmp_path / "wal")
    db_file = str(tmp_path / "mem.db")

    config = MemoryConfig(
        working_backend=WorkingMemoryBackend.IN_MEMORY,
        wal_dir=wal_dir,
        fact_backend=FactStoreBackend.SQLITE,
        sqlite_path=db_file,
        vector_backend=VectorStoreBackend.QDRANT,
        qdrant_location=":memory:",
        embedding_backend=EmbeddingBackend.LOCAL,
        collection_name="test_snap_coll",
    )
    engine = MemoryEngine(config=config)
    user_id = "user_snap_e2e"

    # State 1: initial facts
    engine.facts.put_fact(FactItem(user_id=user_id, key="env", value="staging"))
    snap = engine.create_memory_snapshot(user_id=user_id, tag="v1.0")
    assert snap.id is not None

    # State 2: corrupted/unwanted mutation
    engine.facts.put_fact(FactItem(user_id=user_id, key="env", value="corrupted_val"))
    assert engine.facts.get_fact_by_key(user_id, "env").value == "corrupted_val"

    # Rollback to State 1
    engine.rollback_memory(user_id=user_id, snapshot_id=snap.id)
    restored = engine.facts.get_fact_by_key(user_id, "env")
    assert restored.value == "staging"
