"""Unit tests for SQLite FTS5 lexical indexing, exact matching, and prefix search."""

import pytest
from search.core.models import CorpusType, SearchDocument, SearchQuery
from search.engines.local_hybrid import LocalHybridSearchEngine


@pytest.fixture
def search_engine(tmp_path):
    db_file = str(tmp_path / "search_fts.db")
    return LocalHybridSearchEngine(db_path=db_file)


def test_fts_exact_matching_and_prefix(search_engine):
    doc1 = SearchDocument(
        id="doc:1",
        corpus_type=CorpusType.FILE,
        project_id="proj_alpha",
        title="Distributed Consensus Architecture",
        content="Raft protocol relies on leader election and log replication across clusters.",
        tags=["consensus", "architecture"],
    )
    doc2 = SearchDocument(
        id="doc:2",
        corpus_type=CorpusType.NOTE,
        project_id="proj_alpha",
        title="PostgreSQL Tuning Guide",
        content="Optimizing shared buffers, work mem, and WAL checkpoints for high write loads.",
        tags=["database", "postgres"],
    )

    search_engine.index_batch([doc1, doc2])

    # 1. Exact term search: 'raft'
    q1 = SearchQuery(query_text="Raft", project_id="proj_alpha", hybrid_alpha=0.0)
    res1 = search_engine.search(q1)
    assert res1.total_hits >= 1
    assert res1.results[0].document.id == "doc:1"

    # 2. Prefix term search: 'distrib*'
    q2 = SearchQuery(query_text="distrib", project_id="proj_alpha", hybrid_alpha=0.0)
    res2 = search_engine.search(q2)
    assert res2.total_hits >= 1
    assert res2.results[0].document.id == "doc:1"

    # 3. Multi-term query: 'WAL checkpoints'
    q3 = SearchQuery(query_text="WAL checkpoints", project_id="proj_alpha", hybrid_alpha=0.0)
    res3 = search_engine.search(q3)
    assert res3.total_hits >= 1
    assert res3.results[0].document.id == "doc:2"


def test_document_deletion_removes_from_fts(search_engine):
    doc = SearchDocument(
        id="doc:to_del",
        corpus_type=CorpusType.NOTE,
        project_id="proj_test",
        title="Ephemeral Note",
        content="This content should disappear after deletion.",
    )
    search_engine.index_document(doc)

    # Verify present
    res = search_engine.search(SearchQuery(query_text="Ephemeral", project_id="proj_test"))
    assert res.total_hits == 1

    # Delete
    deleted = search_engine.delete_document("doc:to_del")
    assert deleted is True

    # Verify removed
    res_after = search_engine.search(SearchQuery(query_text="Ephemeral", project_id="proj_test"))
    assert res_after.total_hits == 0
