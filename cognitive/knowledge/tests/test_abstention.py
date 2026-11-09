"""Unit and integration tests for Abstention Logic & Hallucination Prevention (Feature 3.35)."""

import pytest
from knowledge.abstention import (
    AbstentionEngine,
    AbstentionVerdict,
    GroundingEvidenceEvaluator,
)


def test_abstention_on_empty_evidence():
    engine = AbstentionEngine()
    result = engine.evaluate_grounding("What is the capital of Atlantis?", [])

    assert result.verdict == AbstentionVerdict.ABSTAIN
    assert result.confidence_score == 0.0
    assert "No evidence passages" in result.reason
    assert "cannot answer" in result.abstention_message.lower()


def test_abstention_on_irrelevant_evidence():
    engine = AbstentionEngine(default_threshold=0.6)
    evidence = [
        "Photosynthesis is a process used by plants to convert light energy into chemical energy.",
        "Chlorophyll absorbs blue and red light while reflecting green.",
    ]
    query = "How do we configure high availability Kubernetes clusters with etcd?"

    result = engine.evaluate_grounding(query, evidence)

    assert result.verdict == AbstentionVerdict.ABSTAIN
    assert result.confidence_score < 0.6
    assert "Insufficient grounding" in result.reason


def test_answer_when_evidence_is_sufficient():
    engine = AbstentionEngine(default_threshold=0.65)
    evidence = [
        "Kubernetes high availability requires at least three etcd member nodes for quorum.",
        "Configure etcd peer URLs with TLS encryption and set heartbeating parameters.",
    ]
    query = "What is required for Kubernetes high availability and etcd nodes?"

    result = engine.evaluate_grounding(query, evidence)

    assert result.verdict == AbstentionVerdict.ANSWER
    assert result.confidence_score >= 0.65
    assert result.abstention_message is None


def test_conflict_penalty_triggers_abstention_or_partial():
    evaluator = GroundingEvidenceEvaluator(default_threshold=0.7)
    conflicting_evidence = [
        "Feature flags are enabled in production by default.",
        "Feature flags are disabled in production and forbidden for standard users.",
    ]
    query = "Are feature flags enabled in production?"

    result = evaluator.evaluate(query, conflicting_evidence)

    assert result.conflict_score > 0.0
    # Confidence is penalized by contradiction
    assert result.verdict in (AbstentionVerdict.PARTIAL, AbstentionVerdict.ABSTAIN)


def test_execute_with_abstention_guards_generator():
    engine = AbstentionEngine(default_threshold=0.65)
    generator_called = False

    def dummy_generator(q, e):
        nonlocal generator_called
        generator_called = True
        return "Hallucinated answer"

    # 1. When evidence is irrelevant -> generator must NOT be called
    res_abstain = engine.execute_with_abstention(
        query="What is the internal architecture of quantum neural networks?",
        evidence_chunks=["Bananas are rich in potassium."],
        generator=dummy_generator,
    )

    assert res_abstain.abstained is True
    assert res_abstain.verdict == AbstentionVerdict.ABSTAIN
    assert generator_called is False
    assert "sufficient verified knowledge" in res_abstain.output_text

    # 2. When evidence is relevant -> generator IS called
    generator_called = False
    res_answer = engine.execute_with_abstention(
        query="What are bananas rich in?",
        evidence_chunks=["Bananas are rich in potassium and dietary fiber."],
        generator=dummy_generator,
    )

    assert res_answer.abstained is False
    assert res_answer.verdict == AbstentionVerdict.ANSWER
    assert generator_called is True
    assert res_answer.output_text == "Hallucinated answer"
