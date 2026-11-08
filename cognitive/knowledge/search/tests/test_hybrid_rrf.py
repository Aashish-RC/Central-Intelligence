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
