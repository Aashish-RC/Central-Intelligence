"""Unit and integration tests for Source Quality & Authority Scorer (Feature 3.43)."""

import pytest
from knowledge.quality import (
    SourceQualityAuthorityScorer,
    SourceQualityTier,
)


def test_authoritative_educational_domain_scores_high():
    scorer = SourceQualityAuthorityScorer()
    source = "https://cs.stanford.edu/research/distributed-systems"
    content = """
    Distributed consensus protocols require rigorous verification of state transitions.
    In this paper we demonstrate Paxos and Raft under partitioned networks with Byzantine faults.
    ```python
    def verify_state_transition(leader_term, log_index):
        return leader_term >= current_term
    ```
    This protocol guarantees safety across all failure modes and prevents split-brain anomalies.
    """

    score = scorer.score_source(source, content, metadata={"published_year": 2025})

    assert score.authority_score >= 0.85
    assert score.overall_score >= 0.80
    assert score.tier == SourceQualityTier.TIER_1_AUTHORITATIVE
    assert any(s.name == "official_tld" for s in score.signals)
    assert any(s.name == "technical_spec_or_code" for s in score.signals)


def test_spam_and_clickbait_penalized_to_low_quality():
    scorer = SourceQualityAuthorityScorer()
    source = "https://crypto-pump-news.biz/post123"
    content = """
    You won't believe this shocking truth! Miracle cure for poverty with guaranteed profit!
    Click here now to participate in our crypto pump casino.
    """

    score = scorer.score_source(source, content)

    assert score.overall_score < 0.50
    assert score.tier in (SourceQualityTier.TIER_3_UNVERIFIED, SourceQualityTier.TIER_4_LOW_QUALITY)
    assert any(s.name == "spam_markers_detected" for s in score.signals)


def test_llm_judge_hook_blending():
    def mock_llm_judge(src: str, text: str):
        if "hallucination" in text:
            return 0.15, "Low factual rigor"
        return 0.95, "Peer-reviewed factual rigor"

    scorer = SourceQualityAuthorityScorer(llm_judge_fn=mock_llm_judge)

    # 1. Rigorous text
    score_good = scorer.score_source(
        "https://nature.com/articles/energy-storage-paper",
        "Thorough scientific study on advanced lithium iron phosphate energy storage architectures and cycling life with experimental benchmarking.",
    )
    assert score_good.llm_judge_verdict == "Peer-reviewed factual rigor"
    assert score_good.overall_score >= 0.70

    # 2. Hallucinatory text
    score_bad = scorer.score_source(
        "https://example.com/unverified",
        "This contains hallucination and made up numbers without any empirical evidence or experimental validation.",
    )
    assert score_bad.llm_judge_verdict == "Low factual rigor"
    assert score_bad.overall_score < score_good.overall_score
