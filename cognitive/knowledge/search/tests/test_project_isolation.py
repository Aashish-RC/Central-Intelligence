"""Unit tests for strict project isolation boundaries in Global Search."""

import pytest
from search.core.models import CorpusType, SearchDocument, SearchQuery
from search.engines.local_hybrid import LocalHybridSearchEngine


@pytest.fixture
def search_engine(tmp_path):
    db_file = str(tmp_path / "search_isolation.db")
    return LocalHybridSearchEngine(db_path=db_file)


def test_project_search_isolation(search_engine):
    doc_a = SearchDocument(
        id="doc:alpha_secret",
        corpus_type=CorpusType.FILE,
        project_id="project_alpha",
        title="Alpha Top Secret Roadmap",
        content="Project Alpha confidential deployment keys and credentials.",
    )
    doc_b = SearchDocument(
        id="doc:beta_secret",
        corpus_type=CorpusType.FILE,
        project_id="project_beta",
        title="Beta Public Notes",
        content="Project Beta documentation and public release roadmap.",
    )

    search_engine.index_batch([doc_a, doc_b])

    # Search in Project Alpha
    res_a = search_engine.search(
        SearchQuery(query_text="roadmap credentials", project_id="project_alpha")
    )
    assert res_a.total_hits == 1
    assert res_a.results[0].document.id == "doc:alpha_secret"
    # Ensure no Beta leak
    for r in res_a.results:
        assert r.document.project_id == "project_alpha"

    # Search in Project Beta
    res_b = search_engine.search(
        SearchQuery(query_text="roadmap credentials", project_id="project_beta")
    )
    assert res_b.total_hits == 1
    assert res_b.results[0].document.id == "doc:beta_secret"
    for r in res_b.results:
        assert r.document.project_id == "project_beta"


def test_delete_by_project_boundary(search_engine):
    doc_a = SearchDocument(
        id="a1", corpus_type=CorpusType.NOTE, project_id="proj_x", title="X note", content="Content X"
    )
    doc_b = SearchDocument(
        id="b1", corpus_type=CorpusType.NOTE, project_id="proj_y", title="Y note", content="Content Y"
    )
    search_engine.index_batch([doc_a, doc_b])

    # Delete proj_x
    deleted_count = search_engine.delete_by_project("proj_x")
    assert deleted_count == 1

    # proj_x should be empty
    res_x = search_engine.search(SearchQuery(query_text="Content", project_id="proj_x"))
    assert res_x.total_hits == 0

    # proj_y remains intact
    res_y = search_engine.search(SearchQuery(query_text="Content", project_id="proj_y"))
    assert res_y.total_hits == 1
    assert res_y.results[0].document.id == "b1"
