"""Tests for Permission-Filtered Retrieval (Task 12.13, Feature 3.36 — DEF-02 UNBLOCKED)."""

import pytest
from cognitive.knowledge.access_control.openfga_bridge import (
    check_document_access,
    filter_results_by_permission,
)
from cognitive.knowledge.search.core.models import (
    CorpusType,
    SearchDocument,
    SearchQuery,
    SearchResult,
)
from cognitive.knowledge.search.engines.local_hybrid import LocalHybridSearchEngine
from control.identity.openfga_adapter import OpenFGAAdapter, default_openfga_adapter


def test_permission_filtering_rebac_acceptance():
    """Acceptance Test:
    - Alice cannot view doc2; Bob can view doc2.
    - When Alice searches/filters, doc2 is filtered out.
    - When Bob searches/filters, doc2 is returned.
    """
    fga = OpenFGAAdapter()

    # Doc1 is public or accessible to everyone
    # Doc2 is confidential, viewer permission granted ONLY to Bob
    fga.write_tuple(user="user:bob", relation="viewer", object="document:doc2")

    doc1 = SearchDocument(
        id="doc1",
        corpus_type=CorpusType.NOTE,
        title="Public Guidelines",
        content="General guidelines for company employees.",
        metadata={"public": True},
    )
    doc2 = SearchDocument(
        id="doc2",
        corpus_type=CorpusType.NOTE,
        title="Bob Confidential Report",
        content="Secret financial records only Bob can see.",
        metadata={"public": False},
    )

    results = [
        SearchResult(document=doc1, rrf_score=0.9),
        SearchResult(document=doc2, rrf_score=0.8),
    ]

    # Alice filter
    alice_results = filter_results_by_permission(
        results=results,
        user_id="alice",
        openfga_client=fga,
    )
    alice_doc_ids = [r.document.id for r in alice_results]
    assert "doc1" in alice_doc_ids
    assert "doc2" not in alice_doc_ids

    # Bob filter
    bob_results = filter_results_by_permission(
        results=results,
        user_id="bob",
        openfga_client=fga,
    )
    bob_doc_ids = [r.document.id for r in bob_results]
    assert "doc1" in bob_doc_ids
    assert "doc2" in bob_doc_ids


def test_engine_search_permission_filtering():
    """Integration Test: LocalHybridSearchEngine filters documents based on query.user_id."""
    engine = LocalHybridSearchEngine(db_path=":memory:")
    
    # Configure default OpenFGA adapter for Bob
    default_openfga_adapter.write_tuple(user="user:bob", relation="viewer", object="document:sec-doc-42")

    doc_pub = SearchDocument(
        id="pub-doc-1",
        corpus_type=CorpusType.NOTE,
        title="Architecture Overview",
        content="Architecture design documentation.",
        metadata={"public": True},
    )
    doc_priv = SearchDocument(
        id="sec-doc-42",
        corpus_type=CorpusType.NOTE,
        title="Secret Architecture Blueprint",
        content="Confidential architecture blueprint details.",
        metadata={"public": False},
    )

    engine.index_document(doc_pub)
    engine.index_document(doc_priv)

    # Alice searches for architecture
    q_alice = SearchQuery(query_text="architecture", user_id="alice")
    resp_alice = engine.search(q_alice)
    alice_ids = [r.document.id for r in resp_alice.results]
    assert "pub-doc-1" in alice_ids
    assert "sec-doc-42" not in alice_ids

    # Bob searches for architecture
    q_bob = SearchQuery(query_text="architecture", user_id="bob")
    resp_bob = engine.search(q_bob)
    bob_ids = [r.document.id for r in resp_bob.results]
    assert "pub-doc-1" in bob_ids
    assert "sec-doc-42" in bob_ids


if __name__ == "__main__":
    test_permission_filtering_rebac_acceptance()
    print("test_permission_filtering_rebac_acceptance PASSED!")
    test_engine_search_permission_filtering()
    print("test_engine_search_permission_filtering PASSED!")
