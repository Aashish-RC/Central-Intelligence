"""D3 Regression and Hardening Unit Tests.

Validates the 8 critical D3 post-closure retrieval fixes:
1. Complete document deletion across Qdrant, pgvector, and Apache AGE.
2. Project-scoped deletion with tenant boundaries.
3. Explicit eventual consistency with compensating rollback on partial indexing failure.
4. Normal search(SearchQuery) performs vector retrieval via embedder without skipping.
5. Tenant authorization boundary enforcement (rejecting mismatches and invalid IDs).
6. Graph retrieval and enrichment tenant isolation (preventing cross-tenant leakage).
7. Deterministic RRF ranking with stable tie-breaking and deduplication.
8. Backend failure handling: explicit strict failure vs degraded mode reporting.
"""

from __future__ import annotations

from uuid import uuid4
import pytest

from cognitive.knowledge.search.core.models import CorpusType, SearchDocument, SearchQuery, SearchResponse
from cognitive.knowledge.search.engines.integrated_hybrid import (
    IntegratedHybridRetrievalEngine,
    RetrievalBackendError,
)
from cognitive.memory.embeddings.embedder import LocalHashEmbedder
from cognitive.memory.tiers.graph.age_adapter import ApacheAGEAdapter
from cognitive.memory.tiers.semantic.qdrant_adapter import QdrantAdapter
from platform_infra.data.supabase.supabase_adapter import SupabaseAdapter


@pytest.fixture
def test_harness():
    """Sets up an in-memory 3-backend harness for hermetic D3 testing."""
    suffix = uuid4().hex[:8]
    col_name = f"test_col_{suffix}"
    graph_name = f"test_graph_{suffix}"

    qdrant = QdrantAdapter(location=":memory:", collection_name=col_name, dim=4)
    age = ApacheAGEAdapter(postgres_url=":memory:", graph_name=graph_name, auto_fallback=True)
    pgvec = SupabaseAdapter(_defer_prod_check=True)
    pgvec.adapter_mode = "simulated"
    embedder = LocalHashEmbedder(dim=4)

    engine = IntegratedHybridRetrievalEngine(
        qdrant_adapter=qdrant,
        age_adapter=age,
        pgvector_adapter=pgvec,
        rrf_k=60,
        weights=(0.4, 0.4, 0.2),
        strict_backends=True,
        collection_name=col_name,
        embedder=embedder,
    )

    return {
        "engine": engine,
        "qdrant": qdrant,
        "age": age,
        "pgvec": pgvec,
        "embedder": embedder,
        "col_name": col_name,
    }


# ==============================================================================
# 1. Incomplete Document Deletion Fix
# ==============================================================================
def test_d3_01_complete_document_deletion(test_harness):
    """Document deletion must cover Qdrant, Apache AGE, and pgvector; deleted docs cannot reappear."""
    engine = test_harness["engine"]
    pgvec = test_harness["pgvec"]
    col_name = test_harness["col_name"]
    tenant = "tenant_del"

    doc = SearchDocument(
        id="doc_to_delete",
        title="Document To Delete",
        content="This document must be purged from all three backends.",
        tenant_id=tenant,
        project_id="proj_del",
        corpus_type=CorpusType.FILE,
    )
    vec = [1.0, 0.0, 0.0, 0.0]

    engine.index_document(
        doc,
        embedding=vec,
        graph_entities=[{"name": "DeleteEntity", "label": "Test"}],
        graph_relationships=[(doc.id, "REFERENCES", "DeleteEntity")],
    )

    # Verify present across backends
    resp_before = engine.retrieve(query="Document To Delete", tenant_id=tenant, query_embedding=vec)
    assert any(r.document.id == "doc_to_delete" for r in resp_before.results)
    assert len(pgvec.vector_collections.get(f"pgvec_{col_name}", [])) == 1

    # Execute deletion
    deleted = engine.delete_document("doc_to_delete", tenant_id=tenant)
    assert deleted is True

    # Verify document does NOT exist in pgvector
    pg_records = pgvec.vector_collections.get(f"pgvec_{col_name}", [])
    assert not any(r.id == "doc_to_delete" for r in pg_records)

    # Verify document cannot reappear in retrieval
    resp_after = engine.retrieve(query="Document To Delete", tenant_id=tenant, query_embedding=vec)
    assert not any(r.document.id == "doc_to_delete" for r in resp_after.results)


# ==============================================================================
# 2. Project-Scoped Deletion
# ==============================================================================
def test_d3_02_delete_by_project(test_harness):
    """delete_by_project() purges all documents for a project while preserving other projects."""
    engine = test_harness["engine"]
    tenant = "tenant_proj"

    doc_a1 = SearchDocument(
        id="doc_a1", title="Proj A Doc 1", content="Alpha",
        tenant_id=tenant, project_id="proj_alpha", corpus_type=CorpusType.FILE,
    )
    doc_a2 = SearchDocument(
        id="doc_a2", title="Proj A Doc 2", content="Alpha 2",
        tenant_id=tenant, project_id="proj_alpha", corpus_type=CorpusType.FILE,
    )
    doc_b1 = SearchDocument(
        id="doc_b1", title="Proj B Doc 1", content="Beta",
        tenant_id=tenant, project_id="proj_beta", corpus_type=CorpusType.FILE,
    )

    vec = [0.5, 0.5, 0.0, 0.0]
    engine.index_document(doc_a1, embedding=vec)
    engine.index_document(doc_a2, embedding=vec)
    engine.index_document(doc_b1, embedding=vec)

    # Purge project alpha
    deleted_count = engine.delete_by_project(project_id="proj_alpha", tenant_id=tenant)
    assert deleted_count >= 2

    # Verify Proj B survives, Proj A is gone
    resp = engine.retrieve(query="Alpha Beta", tenant_id=tenant, query_embedding=vec)
    hit_ids = [r.document.id for r in resp.results]
    assert "doc_b1" in hit_ids
    assert "doc_a1" not in hit_ids
    assert "doc_a2" not in hit_ids


# ==============================================================================
# 3. Partial Indexing Failure & Compensating Rollback
# ==============================================================================
def test_d3_03_partial_indexing_failure_compensating_cleanup(test_harness, monkeypatch):
    """When a downstream backend fails, compensating cleanup rolls back already-indexed backends."""
    engine = test_harness["engine"]
    age = test_harness["age"]
    pgvec = test_harness["pgvec"]
    col_name = test_harness["col_name"]
    tenant = "tenant_comp"

    # Simulate Apache AGE failure
    def failing_add_entity(*args, **kwargs):
        raise RuntimeError("Simulated Apache AGE graph storage fault")

    monkeypatch.setattr(age, "add_entity", failing_add_entity)

    doc = SearchDocument(
        id="doc_fail_comp",
        title="Failing Doc",
        content="Should trigger compensating cleanup across backends.",
        tenant_id=tenant,
        project_id="proj_fail",
        corpus_type=CorpusType.FILE,
    )

    with pytest.raises(RetrievalBackendError) as exc_info:
        engine.index_document(doc, embedding=[1.0, 0.0, 0.0, 0.0])

    assert exc_info.value.backend == "apache_age"

    # Verify pgvector was compensated (no orphan record left)
    pg_records = pgvec.vector_collections.get(f"pgvec_{col_name}", [])
    assert not any(r.id == "doc_fail_comp" for r in pg_records)


# ==============================================================================
# 4. Normal Search Interface Vector Retrieval
# ==============================================================================
def test_d3_04_normal_search_interface_vector_retrieval(test_harness):
    """search(SearchQuery) must automatically compute embeddings and query vector stores."""
    engine = test_harness["engine"]
    tenant = "tenant_norm"

    doc = SearchDocument(
        id="doc_consensus_search",
        title="Raft Distributed Consensus",
        content="State machine replication algorithm with leader election and log consistency.",
        tenant_id=tenant,
        project_id="proj_search",
        corpus_type=CorpusType.FILE,
    )
    # Let index_document use the engine's embedder
    engine.index_document(doc)

    # Execute search WITHOUT providing query.embedding
    query = SearchQuery(
        query_text="Raft leader election consistency",
        tenant_id=tenant,
        limit=5,
    )
    resp: SearchResponse = engine.search(query)

    assert isinstance(resp, SearchResponse)
    assert resp.total_hits >= 1
    assert resp.results[0].document.id == "doc_consensus_search"
    # Ensure vector_rank was assigned (proves vector store was queried)
    assert resp.results[0].vector_rank is not None


# ==============================================================================
# 5. Tenant Authorization Boundary
# ==============================================================================
def test_d3_05_tenant_authorization_boundary(test_harness):
    """Tenant authorization boundary strictly rejects mismatches, empty IDs, and invalid characters."""
    engine = test_harness["engine"]

    # Mismatch between caller context and query.tenant_id
    with pytest.raises(PermissionError) as exc_info:
        engine.retrieve(
            query=SearchQuery(query_text="query", tenant_id="tenant_attacker"),
            tenant_id="tenant_victim",
        )
    assert "mismatch" in str(exc_info.value).lower()

    # Empty tenant ID
    with pytest.raises(PermissionError):
        engine.retrieve(query="query", tenant_id="")

    # Malicious injection in tenant ID
    for bad_tenant in ["tenant;DROP TABLE", "tenant*", "tenant' OR '1'='1", "tenant/../leak"]:
        with pytest.raises(PermissionError):
            engine.retrieve(query="query", tenant_id=bad_tenant)


# ==============================================================================
# 6. Graph Retrieval Tenant Isolation
# ==============================================================================
def test_d3_06_graph_retrieval_tenant_isolation(test_harness):
    """Graph matches and context enrichment cannot leak entities or relationships from another tenant."""
    engine = test_harness["engine"]
    tenant_a = "tenant_alpha"
    tenant_b = "tenant_beta"

    doc_a = SearchDocument(
        id="doc_a_public", title="Alpha Protocol", content="Public alpha content",
        tenant_id=tenant_a, project_id="proj_a", corpus_type=CorpusType.FILE,
    )
    doc_b = SearchDocument(
        id="doc_b_secret", title="Beta Secret", content="Proprietary beta content",
        tenant_id=tenant_b, project_id="proj_b", corpus_type=CorpusType.FILE,
    )

    vec = [0.8, 0.2, 0.0, 0.0]
    engine.index_document(
        doc_a,
        embedding=vec,
        graph_entities=[{"name": "AlphaNode", "label": "Node"}],
        graph_relationships=[(doc_a.id, "OWNS", "AlphaNode")],
    )
    engine.index_document(
        doc_b,
        embedding=vec,
        graph_entities=[{"name": "BetaSecretNode", "label": "Secret"}],
        graph_relationships=[(doc_b.id, "OWNS", "BetaSecretNode")],
    )

    # Tenant Alpha query
    resp_a = engine.retrieve(query="Alpha Protocol", tenant_id=tenant_a, query_embedding=vec)
    for hit in resp_a.results:
        assert hit.document.tenant_id == tenant_a
        assert hit.document.id != doc_b.id
        enrichment = hit.document.metadata.get("graph_enrichment", [])
        for edge in enrichment:
            assert "BetaSecretNode" not in str(edge)


# ==============================================================================
# 7. Deterministic Ranking & Stable Tie-Breaking
# ==============================================================================
def test_d3_07_deterministic_ranking_tie_breaking(test_harness):
    """Candidates with equal RRF scores must have deterministic, repeatable ordering across queries."""
    engine = test_harness["engine"]
    tenant = "tenant_rrf"

    # Insert two documents with identical vector & content
    doc_z = SearchDocument(id="doc_z_item", title="Same Item Z", content="Identical body", tenant_id=tenant, corpus_type=CorpusType.FILE)
    doc_a = SearchDocument(id="doc_a_item", title="Same Item A", content="Identical body", tenant_id=tenant, corpus_type=CorpusType.FILE)

    vec = [0.9, 0.1, 0.0, 0.0]
    engine.index_document(doc_z, embedding=vec)
    engine.index_document(doc_a, embedding=vec)

    # Multiple query executions must yield identical deterministic order
    resp1 = engine.retrieve(query="Identical body", tenant_id=tenant, query_embedding=vec, top_k=5)
    resp2 = engine.retrieve(query="Identical body", tenant_id=tenant, query_embedding=vec, top_k=5)

    order1 = [r.document.id for r in resp1.results]
    order2 = [r.document.id for r in resp2.results]

    assert order1 == order2
    # Tie-breaking on doc_id guarantees doc_a_item comes before doc_z_item
    assert order1[0] == "doc_a_item"
    assert order1[1] == "doc_z_item"


# ==============================================================================
# 8. Backend Failure Handling: Strict vs Degraded Mode
# ==============================================================================
def test_d3_08_backend_failure_handling(test_harness, monkeypatch):
    """Strict mode fails explicitly on backend errors, while non-strict mode accurately reports degraded contributions."""
    engine_strict = test_harness["engine"]
    qdrant = test_harness["qdrant"]
    tenant = "tenant_degrade"

    def failing_query_similar(*args, **kwargs):
        raise ConnectionError("Qdrant backend disconnected")

    monkeypatch.setattr(qdrant, "query_similar", failing_query_similar)

    # 1. Strict mode must raise RetrievalBackendError
    with pytest.raises(RetrievalBackendError) as exc_info:
        engine_strict.retrieve(query="test", tenant_id=tenant, query_embedding=[1.0, 0.0, 0.0, 0.0])
    assert exc_info.value.backend == "qdrant"

    # 2. Non-strict mode must return degraded response with -1 contribution
    engine_degraded = IntegratedHybridRetrievalEngine(
        qdrant_adapter=qdrant,
        age_adapter=test_harness["age"],
        pgvector_adapter=test_harness["pgvec"],
        strict_backends=False,
        embedder=test_harness["embedder"],
    )

    resp = engine_degraded.retrieve(query="test", tenant_id=tenant, query_embedding=[1.0, 0.0, 0.0, 0.0])
    assert resp.degraded is True
    assert resp.backend_contributions["qdrant"] == -1


# ==============================================================================
# 9. Tenant-Safe Deletion: Context Rejection
# ==============================================================================
def test_d3_09_tenant_safe_deletion_rejects_unauthorized_contexts(test_harness):
    """Document and project deletion must strictly reject missing, wildcard, or mismatched tenants."""
    engine = test_harness["engine"]

    # 1. Missing / None tenant
    with pytest.raises(PermissionError):
        engine.delete_document("doc1", tenant_id=None)
    with pytest.raises(PermissionError):
        engine.delete_by_project("proj1", tenant_id=None)

    # 2. Empty string
    with pytest.raises(PermissionError):
        engine.delete_document("doc1", tenant_id="")
    with pytest.raises(PermissionError):
        engine.delete_by_project("proj1", tenant_id="")

    # 3. Wildcard tenant
    with pytest.raises(PermissionError):
        engine.delete_document("doc1", tenant_id="*")
    with pytest.raises(PermissionError):
        engine.delete_by_project("proj1", tenant_id="*")

    # 4. Mismatched caller context vs target tenant
    with pytest.raises(PermissionError):
        engine.delete_document("doc1", tenant_id="tenant_a", caller_tenant_id="tenant_b")
    with pytest.raises(PermissionError):
        engine.delete_by_project("proj1", tenant_id="tenant_a", caller_tenant_id="tenant_b")


# ==============================================================================
# 10. Tenant-Safe Deletion: Cross-Tenant Isolation
# ==============================================================================
def test_d3_10_tenant_safe_deletion_cross_tenant_isolation(test_harness):
    """Deletion by Tenant Beta must not delete Tenant Alpha's documents or project records in Qdrant, pgvec, or AGE."""
    engine = test_harness["engine"]
    tenant_a = "tenant_alpha"
    tenant_b = "tenant_beta"
    vec = [0.9, 0.1, 0.0, 0.0]

    doc_a = SearchDocument(
        id="doc_alpha_secure",
        title="Alpha Secure Doc",
        content="Tenant Alpha proprietary content",
        tenant_id=tenant_a,
        project_id="proj_shared_id",
        corpus_type=CorpusType.FILE,
    )
    engine.index_document(doc_a, embedding=vec, graph_entities=[{"name": "AlphaEntity", "label": "Secret"}])

    # Prove doc_a exists
    res_a = engine.retrieve(query="Alpha", tenant_id=tenant_a, query_embedding=vec, top_k=5)
    assert any(r.document.id == "doc_alpha_secure" for r in res_a.results)

    # Tenant Beta attempts to delete Tenant Alpha's document
    # With tenant_b context, it must not delete doc_a
    del_res = engine.delete_document("doc_alpha_secure", tenant_id=tenant_b)
    # Deletion targeted at doc_alpha_secure with tenant_b context affects 0 records
    assert del_res is False

    # Verify doc_a is STILL present and retrievable by Tenant Alpha
    res_a_post = engine.retrieve(query="Alpha", tenant_id=tenant_a, query_embedding=vec, top_k=5)
    assert any(r.document.id == "doc_alpha_secure" for r in res_a_post.results)

    # Tenant Beta attempts to purge proj_shared_id
    del_proj = engine.delete_by_project("proj_shared_id", tenant_id=tenant_b)
    assert del_proj == 0

    # Verify doc_a is STILL present and retrievable by Tenant Alpha
    res_a_after_proj = engine.retrieve(query="Alpha", tenant_id=tenant_a, query_embedding=vec, top_k=5)
    assert any(r.document.id == "doc_alpha_secure" for r in res_a_after_proj.results)


# ==============================================================================
# 11. Apache AGE Partial-Write Recovery: Node and Relationship Rollback
# ==============================================================================
def test_d3_11_age_partial_write_recovery_removes_partially_created_nodes_and_relationships(test_harness, monkeypatch):
    """When graph indexing fails midway, partially created nodes/edges are rolled back, while pre-existing entities are preserved."""
    engine = test_harness["engine"]
    age = test_harness["age"]
    qdrant = test_harness["qdrant"]
    pgvec = test_harness["pgvec"]
    tenant = "tenant_recovery"
    project_id = "proj_rec"
    vec = [0.7, 0.7, 0.0, 0.0]

    # Pre-seed a shared graph entity for this tenant
    shared_entity = "SharedProtocol"
    age.add_entity(user_id=tenant, name=shared_entity, entity_type="Protocol", project_id=project_id)
    assert age.entity_exists(tenant, shared_entity, project_id) is True

    # Now attempt to index a document with the pre-existing entity + a new entity + relationships
    doc = SearchDocument(
        id="doc_fail_stage3",
        title="Failing Document",
        content="Content intended for rollback test",
        tenant_id=tenant,
        project_id=project_id,
        corpus_type=CorpusType.FILE,
    )
    graph_entities = [
        {"name": shared_entity, "label": "Protocol"},
        {"name": "NewTempEntity", "label": "Temp"},
    ]
    graph_rels = [
        (doc.id, "SPECIFIES", shared_entity),
        (doc.id, "CREATES", "NewTempEntity"),
    ]

    original_add_rel = age.add_relationship
    call_count = 0

    def failing_add_relationship(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise RuntimeError("Injected database error during relationship indexing")
        return original_add_rel(*args, **kwargs)

    monkeypatch.setattr(age, "add_relationship", failing_add_relationship)

    with pytest.raises(RetrievalBackendError) as exc_info:
        engine.index_document(
            doc,
            embedding=vec,
            graph_entities=graph_entities,
            graph_relationships=graph_rels,
        )
    assert exc_info.value.backend == "apache_age"

    # Consistency verifications:
    # 1. Pre-existing shared entity MUST still exist
    assert age.entity_exists(tenant, shared_entity, project_id) is True

    # 2. Newly created entity must be removed by compensating rollback
    assert age.entity_exists(tenant, "NewTempEntity", project_id) is False

    # 3. Document root node must be removed by compensating rollback
    assert age.entity_exists(tenant, doc.id, project_id) is False

    # 4. First relationship must be removed
    rel_check = age.multi_hop_query(tenant, doc.id, hops=1, project_id=project_id)
    assert len(rel_check) == 0

    # 5. Qdrant must be rolled back (0 points)
    q_hits = qdrant.query_similar(user_id=tenant, query_embedding=vec, top_k=5)
    assert not any(r.metadata.get("doc_id") == doc.id for r in q_hits)

    # 6. pgvector must be rolled back (0 embeddings)
    pg_hits = pgvec.search_embeddings(
        collection=f"pgvec_{test_harness['col_name']}",
        query_vector=vec,
        top_k=5,
        user_id=tenant,
    )
    assert not any(r.get("id") == doc.id for r in pg_hits)


# ==============================================================================
# 12. Failure Injection at Each Indexing Stage
# ==============================================================================
def test_d3_12_failure_injection_at_each_graph_indexing_stage(test_harness, monkeypatch):
    """Failure injection at each stage (Qdrant, pgvector, AGE root node, AGE auxiliary entity) ensures complete cross-backend consistency."""
    engine = test_harness["engine"]
    qdrant = test_harness["qdrant"]
    pgvec = test_harness["pgvec"]
    age = test_harness["age"]
    tenant = "tenant_stages"
    project_id = "proj_stages"
    vec = [0.5, 0.5, 0.5, 0.5]

    # Pre-existing shared entity
    age.add_entity(user_id=tenant, name="CoreStandard", entity_type="Standard", project_id=project_id)

    # --- Test Failure at Stage 1 (Qdrant) ---
    doc1 = SearchDocument(
        id="doc_fail_stage1",
        title="Fail Qdrant",
        content="Test",
        tenant_id=tenant,
        project_id=project_id,
        corpus_type=CorpusType.FILE,
    )
    monkeypatch.setattr(qdrant, "upsert_vectors", lambda records: (_ for _ in ()).throw(RuntimeError("Qdrant write error")))
    with pytest.raises(RetrievalBackendError) as exc1:
        engine.index_document(doc1, embedding=vec)
    assert exc1.value.backend == "qdrant"
    assert not any(r.get("id") == doc1.id for r in pgvec.search_embeddings(f"pgvec_{test_harness['col_name']}", vec, top_k=5, user_id=tenant))
    assert age.entity_exists(tenant, doc1.id, project_id) is False

    # --- Test Failure at Stage 2 (pgvector) ---
    monkeypatch.undo()
    doc2 = SearchDocument(
        id="doc_fail_stage2",
        title="Fail pgvector",
        content="Test",
        tenant_id=tenant,
        project_id=project_id,
        corpus_type=CorpusType.FILE,
    )
    monkeypatch.setattr(pgvec, "store_embedding", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("pgvector connection dropped")))
    with pytest.raises(RetrievalBackendError) as exc2:
        engine.index_document(doc2, embedding=vec)
    assert exc2.value.backend == "pgvector"
    # Qdrant must be rolled back
    assert not any(r.metadata.get("doc_id") == doc2.id for r in qdrant.query_similar(tenant, vec, top_k=5))
    assert age.entity_exists(tenant, doc2.id, project_id) is False

    # --- Test Failure at Stage 3a (AGE: root document node addition) ---
    monkeypatch.undo()
    doc3 = SearchDocument(
        id="doc_fail_stage3a",
        title="Fail AGE Root",
        content="Test",
        tenant_id=tenant,
        project_id=project_id,
        corpus_type=CorpusType.FILE,
    )
    orig_add_entity = age.add_entity
    def fail_root_entity(user_id, name, *args, **kwargs):
        if name == doc3.id:
            raise RuntimeError("AGE root node error")
        return orig_add_entity(user_id, name, *args, **kwargs)
    monkeypatch.setattr(age, "add_entity", fail_root_entity)

    with pytest.raises(RetrievalBackendError) as exc3a:
        engine.index_document(doc3, embedding=vec)
    assert exc3a.value.backend == "apache_age"
    # Qdrant and pgvector must be rolled back
    assert not any(r.metadata.get("doc_id") == doc3.id for r in qdrant.query_similar(tenant, vec, top_k=5))
    assert not any(r.get("id") == doc3.id for r in pgvec.search_embeddings(f"pgvec_{test_harness['col_name']}", vec, top_k=5, user_id=tenant))

    # --- Test Failure at Stage 3b (AGE: auxiliary entity addition halfway) ---
    monkeypatch.undo()
    doc4 = SearchDocument(
        id="doc_fail_stage3b",
        title="Fail AGE Aux",
        content="Test",
        tenant_id=tenant,
        project_id=project_id,
        corpus_type=CorpusType.FILE,
    )
    orig_add_entity2 = age.add_entity
    def fail_aux_entity(user_id, name, *args, **kwargs):
        if name == "UnstableEntity":
            raise RuntimeError("AGE aux entity failure")
        return orig_add_entity2(user_id, name, *args, **kwargs)
    monkeypatch.setattr(age, "add_entity", fail_aux_entity)

    with pytest.raises(RetrievalBackendError) as exc3b:
        engine.index_document(
            doc4,
            embedding=vec,
            graph_entities=[
                {"name": "CoreStandard", "label": "Standard"},
                {"name": "FirstNewEntity", "label": "Valid"},
                {"name": "UnstableEntity", "label": "Invalid"},
            ],
        )
    assert exc3b.value.backend == "apache_age"

    # Pre-existing CoreStandard must be preserved
    assert age.entity_exists(tenant, "CoreStandard", project_id) is True
    # Newly added FirstNewEntity must be rolled back
    assert age.entity_exists(tenant, "FirstNewEntity", project_id) is False
    # Root doc4 node must be rolled back
    assert age.entity_exists(tenant, doc4.id, project_id) is False
    # Qdrant and pgvector rolled back
    assert not any(r.metadata.get("doc_id") == doc4.id for r in qdrant.query_similar(tenant, vec, top_k=5))
    assert not any(r.get("id") == doc4.id for r in pgvec.search_embeddings(f"pgvec_{test_harness['col_name']}", vec, top_k=5, user_id=tenant))
