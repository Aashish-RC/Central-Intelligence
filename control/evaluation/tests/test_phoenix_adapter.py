"""Unit tests for Arize Phoenix Adapter (Layer 11, Task 11.1)."""

import pytest
from control.evaluation.phoenix.phoenix_adapter import (
    PhoenixAdapter,
    PhoenixTrace,
    PhoenixSpan,
    HallucinationEvaluation,
    DriftReport,
)


@pytest.fixture
def adapter():
    return PhoenixAdapter(endpoint="http://localhost:6006", hallucination_threshold=0.5)


def test_trace_creation_and_span_completion_acceptance(adapter):
    """Task 11.1 Acceptance: Multi-step agent trace capture with OTel spans."""
    trace = adapter.start_trace(
        name="financial_portfolio_optimization",
        session_id="sess_phoenix_001",
        user_id="user_bob",
        attributes={"tenant": "finance_corp"},
    )
    assert trace.trace_id is not None

    # Step 1: Retrieval Span
    span_retrieval = trace.add_span(
        name="retrieval",
        input_payload={"query": "tech stocks Q3"},
    )
    span_retrieval.complete(output={"chunks_retrieved": 3}, status="ok")

    # Step 2: Model Reasoning Span
    span_reasoning = trace.add_span(
        name="reasoning",
        parent_id=span_retrieval.span_id,
        input_payload={"prompt_tokens": 150},
    )
    span_reasoning.complete(output={"recommendation": "Hold AAPL"}, status="ok")

    stored = adapter.get_trace(trace.trace_id)
    assert stored is not None
    assert len(stored.spans) == 2
    assert stored.spans[0].name == "retrieval"
    assert stored.spans[0].status == "ok"
    assert stored.spans[1].parent_id == stored.spans[0].span_id


def test_hallucination_evaluation_grounded(adapter):
    """Feature 11.01/Task 11.1: Response supported by retrieved context gets clean score."""
    retrieved_context = [
        "Project Aevum is an autonomous cognitive AI operating system created by the Deepmind team.",
        "It features 12 specialized architectural layers for reasoning, safety, memory, and orchestration.",
    ]
    query = "What is Project Aevum?"
    response = (
        "Project Aevum is an autonomous cognitive AI operating system created by the Deepmind team. "
        "It features 12 specialized architectural layers."
    )

    eval_result = adapter.evaluate_hallucination(
        query=query,
        response=response,
        retrieved_context=retrieved_context,
    )

    assert eval_result.is_hallucinated is False
    assert eval_result.grounding_score >= 0.8
    assert eval_result.hallucination_rate <= 0.2
    assert len(eval_result.unsupported_claims) == 0


def test_hallucination_evaluation_unsupported_claims_flagged(adapter):
    """Feature 11.01/Task 11.1: Response with invented claims is flagged as hallucinated."""
    retrieved_context = [
        "Qdrant is a vector similarity search engine running on port 6333.",
    ]
    query = "What database is used and what is its quantum compression ratio?"
    # Model fabricates unsupported claims about quantum teleportation
    response = (
        "Qdrant operates with quantum teleportation compression algorithms achieving 999x reduction. "
        "It is built entirely in Haskell."
    )

    eval_result = adapter.evaluate_hallucination(
        query=query,
        response=response,
        retrieved_context=retrieved_context,
    )

    assert eval_result.is_hallucinated is True
    assert eval_result.hallucination_rate >= 0.5
    assert len(eval_result.unsupported_claims) >= 1
    assert any("quantum" in c.lower() for c in eval_result.unsupported_claims)


def test_embedding_drift_detection(adapter):
    """Task 11.1: Centroid drift detection between baseline and production embeddings."""
    baseline = [
        [0.1, 0.2, 0.3],
        [0.12, 0.22, 0.31],
        [0.09, 0.19, 0.29],
    ]
    # Small variance -> no drift
    stable_current = [
        [0.11, 0.21, 0.30],
        [0.10, 0.20, 0.31],
    ]
    report_stable = adapter.detect_embedding_drift(baseline, stable_current, threshold=0.15)
    assert report_stable.drift_detected is False

    # Significant shift -> drift detected
    shifted_current = [
        [0.9, 0.8, 0.7],
        [0.85, 0.95, 0.75],
    ]
    report_shifted = adapter.detect_embedding_drift(baseline, shifted_current, threshold=0.15)
    assert report_shifted.drift_detected is True
    assert "recalibration" in report_shifted.recommendation.lower()

