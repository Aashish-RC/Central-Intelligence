"""Unit tests for Reciprocal Rank Fusion (RRF) combiner and hybrid score blending."""

import pytest
from search.core.models import CorpusType, SearchDocument
from search.engines.rrf import ReciprocalRankFusion


@pytest.fixture
def rrf():
    return ReciprocalRankFusion()


def test_rrf_blending_formula(rrf):
    doc_a = SearchDocument(id="doc:A", corpus_type=CorpusType.FILE, title="A", content="Content A")
    doc_b = SearchDocument(id="doc:B", corpus_type=CorpusType.NOTE, title="B", content="Content B")
    doc_c = SearchDocument(id="doc:C", corpus_type=CorpusType.CHAT, title="C", content="Content C")

    # Lexical ranks: A (rank 1), B (rank 2)
    lexical_hits = [(doc_a, 10.0), (doc_b, 5.0)]
    # Vector ranks: B (rank 1), C (rank 2)
    vector_hits = [(doc_b, 0.95), (doc_c, 0.85)]

    # Fuse with k=60, alpha=0.5
    results = rrf.fuse(lexical_hits, vector_hits, k=60, alpha=0.5, limit=5)

    assert len(results) == 3
    # doc_B is present in both lists (rank 2 lexical, rank 1 vector)
    # Expected score for B: 0.5 * (1/(60+2)) + 0.5 * (1/(60+1)) = 0.5/62 + 0.5/61 ~= 0.008064 + 0.008196 = 0.016260
    # Expected score for A: 0.5 * (1/(60+1)) = 0.5/61 ~= 0.008196
    # Expected score for C: 0.5 * (1/(60+2)) = 0.5/62 ~= 0.008064
    # Therefore doc_b should rank 1st overall!
    assert results[0].document.id == "doc:B"
    assert results[0].lexical_rank == 2
    assert results[0].vector_rank == 1

    assert results[1].document.id == "doc:A"
    assert results[2].document.id == "doc:C"


def test_rrf_pure_lexical_weighting(rrf):
    doc_a = SearchDocument(id="doc:A", corpus_type=CorpusType.FILE, title="A", content="Content A")
    doc_b = SearchDocument(id="doc:B", corpus_type=CorpusType.FILE, title="B", content="Content B")

    lexical_hits = [(doc_a, 10.0)]
    vector_hits = [(doc_b, 0.99)]

    # alpha = 0.0 (pure lexical): doc_b gets 0 score from vector
    results = rrf.fuse(lexical_hits, vector_hits, k=60, alpha=0.0)
    assert len(results) == 2
    assert results[0].document.id == "doc:A"
    assert results[0].rrf_score > results[1].rrf_score


def test_rrf_three_source_fusion(rrf):
    """Test 3-source RRF fusion across Lexical, Vector, and Graph hits."""
    doc_a = SearchDocument(id="doc:A", corpus_type=CorpusType.FILE, title="A", content="Content A")
    doc_b = SearchDocument(id="doc:B", corpus_type=CorpusType.NOTE, title="B", content="Content B")
    doc_c = SearchDocument(id="doc:C", corpus_type=CorpusType.CHAT, title="C", content="Content C")
    doc_g = SearchDocument(id="doc:G", corpus_type=CorpusType.MEMORY, title="G", content="Graph Entity Doc")

    lexical_hits = [(doc_a, 10.0), (doc_b, 5.0)]
    vector_hits = [(doc_b, 0.95), (doc_c, 0.85)]
    graph_hits = [(doc_g, 1.0), (doc_b, 0.8)]

    # 3-source fusion with explicit weights
    results = rrf.fuse(
        lexical_hits=lexical_hits,
        vector_hits=vector_hits,
        graph_hits=graph_hits,
        k=60,
        weights=(0.3, 0.3, 0.4),
        limit=5,
    )

    assert len(results) == 4
    # doc_B has ranks in all 3 sources (lexical: 2, vector: 1, graph: 2) -> ranks highest overall
    assert results[0].document.id == "doc:B"
    assert results[0].lexical_rank == 2
    assert results[0].vector_rank == 1
    assert results[0].graph_rank == 2

    # doc_G has graph rank 1
    doc_g_res = next(r for r in results if r.document.id == "doc:G")
    assert doc_g_res.graph_rank == 1


def test_falkordb_multihop_acquisitions_query():
    """Test GraphRAG FalkorDB adapter: 'What companies does Alice's manager's company acquire?'"""
    from knowledge.graph.falkordb_adapter import FalkorDBAdapter

    adapter = FalkorDBAdapter(host=":memory:")
    assert adapter.check_health() is True

    # 1. Bob manages Alice
    adapter.add_relationship(source="Bob", relation="MANAGES", target="Alice")

    # 2. Bob works at Megacorp
    adapter.add_relationship(source="Bob", relation="WORKS_AT", target="Megacorp")

    # 3. Megacorp acquired StartupAI and DataCloud
    adapter.add_relationship(source="Megacorp", relation="ACQUIRED", target="StartupAI")
    adapter.add_relationship(source="Megacorp", relation="ACQUIRED", target="DataCloud")

    # GraphRAG multi-hop query
    acquisitions = adapter.query_manager_company_acquisitions(employee_name="Alice")
    assert "StartupAI" in acquisitions
    assert "DataCloud" in acquisitions

    # Cypher query test
    cypher_results = adapter.execute_query(
        "MATCH (c)-[:ACQUIRED]->(target) RETURN target.name AS acquired_company"
    )
    acquired_names = [r["acquired_company"] for r in cypher_results]
    assert "StartupAI" in acquired_names
    assert "DataCloud" in acquired_names
