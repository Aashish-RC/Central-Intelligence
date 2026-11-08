"""Unit tests for Multi-Corpus indexing and cross-domain global search."""

import pytest
from search.core.models import CorpusType
from search.indexer.corpus_indexer import CorpusIndexer
from search.engines.local_hybrid import LocalHybridSearchEngine


@pytest.fixture
def indexer(tmp_path):
    db_file = str(tmp_path / "multi_corpus.db")
    engine = LocalHybridSearchEngine(db_path=db_file)
    return CorpusIndexer(engine=engine)


def test_multi_corpus_indexing_and_search(indexer):
    proj = "proj_fusion"

    # 1. Chat turn
    indexer.index_chat_message(
        message_id="msg_001",
        session_id="sess_alpha",
        role="user",
        text="Can we enable AES-256-GCM encryption on the key vault?",
        project_id=proj,
    )

    # 2. File
    indexer.index_storage_file(
        file_id="file_001",
        filename="security_spec.md",
        content_summary="Cryptographic vault specification using AES-256-GCM and Argon2id derivation.",
        sha256="abc1234567890",
        project_id=proj,
        tags=["crypto", "security"],
    )

    # 3. Note
    indexer.index_knowledge_note(
        note_id="note_001",
        title="Security Hardening Guidelines",
        content="Guidelines for deploying secure AES-256-GCM vault endpoints in production.",
        project_id=proj,
        tags=["security", "guidelines"],
    )

    # 4. Memory fact
    indexer.index_memory_fact(
        fact_id="fact_001",
        key="encryption_algorithm",
        value="AES-256-GCM",
        project_id=proj,
        category="security",
    )

    # Global query for 'AES-256-GCM'
    res = indexer.search(query_text="AES-256-GCM", project_id=proj)
    assert res.total_hits >= 4

    found_corpora = set(r.document.corpus_type for r in res.results)
    assert CorpusType.CHAT in found_corpora
    assert CorpusType.FILE in found_corpora
    assert CorpusType.NOTE in found_corpora
    assert CorpusType.MEMORY in found_corpora


def test_corpus_filtering_and_tag_faceting(indexer):
    proj = "proj_filter"

    indexer.index_storage_file(
        file_id="f1",
        filename="auth_service.go",
        content_summary="Authentication token verification and device fingerprinting.",
        sha256="1111",
        project_id=proj,
        tags=["auth", "backend"],
    )

    indexer.index_knowledge_note(
        note_id="n1",
        title="Authentication Flows",
        content="OAuth2 and device fingerprinting diagrams.",
        project_id=proj,
        tags=["auth", "architecture"],
    )

    indexer.index_chat_message(
        message_id="m1",
        session_id="s1",
        role="assistant",
        text="The authentication service is healthy.",
        project_id=proj,
    )

    # 1. Filter by CorpusType.NOTE only
    res_notes = indexer.search(
        query_text="Authentication",
        project_id=proj,
        corpus_types=[CorpusType.NOTE],
    )
    assert res_notes.total_hits == 1
    assert res_notes.results[0].document.corpus_type == CorpusType.NOTE

    # 2. Filter by tag 'backend'
    res_tags = indexer.search(
        query_text="Authentication",
        project_id=proj,
        tags=["backend"],
    )
    assert res_tags.total_hits == 1
    assert res_tags.results[0].document.id == "file:f1"
