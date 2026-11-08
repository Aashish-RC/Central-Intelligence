"""Tests for TelemetryScorer."""

import pytest
from recommender.core.models import (
    CandidateMetrics,
    ModelCandidate,
    OptimizationGoal,
    TaskProfile,
    TaskType,
    ToolCandidate,
)
from recommender.engine.telemetry_scorer import TelemetryScorer


@pytest.fixture
def fast_model():
    return ModelCandidate(
        provider="ollama",
        model_name="qwen-2.5-7b",
        capabilities=["chat", "fast"],
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        metrics=CandidateMetrics(
            total_invocations=50,
            successful_invocations=49,
            avg_latency_ms=120.0,
            quality_score=0.80,
        ),
    )


@pytest.fixture
def premium_model():
    return ModelCandidate(
        provider="anthropic",
        model_name="claude-3-5-sonnet",
        capabilities=["reasoning", "coding", "chat"],
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        metrics=CandidateMetrics(
            total_invocations=100,
            successful_invocations=99,
            avg_latency_ms=850.0,
            quality_score=0.96,
        ),
    )


def test_scorer_min_cost_goal(fast_model, premium_model):
    scorer = TelemetryScorer()
    task = TaskProfile(
        task_id="t1",
        task_type=TaskType.FAST_QUERY,
        goal=OptimizationGoal.MIN_COST,
    )

    fast_score = scorer.score_model(fast_model, task)
    prem_score = scorer.score_model(premium_model, task)

    # Fast model has zero cost, should have higher cost_score and composite_score under MIN_COST
    assert fast_score.cost_score > prem_score.cost_score
    assert fast_score.composite_score > prem_score.composite_score


def test_scorer_max_quality_goal(fast_model, premium_model):
    scorer = TelemetryScorer()
    task = TaskProfile(
        task_id="t2",
        task_type=TaskType.REASONING,
        goal=OptimizationGoal.MAX_QUALITY,
        required_capabilities=["reasoning", "coding"],
    )

    fast_score = scorer.score_model(fast_model, task)
    prem_score = scorer.score_model(premium_model, task)

    # Premium model has required reasoning & coding capabilities and higher quality_score
    assert prem_score.quality_score > fast_score.quality_score
    assert prem_score.composite_score > fast_score.composite_score


def test_scorer_ema_record_execution(fast_model):
    scorer = TelemetryScorer(ema_alpha=0.5)
    cid = fast_model.candidate_id

    # Record 3 fast, successful calls
    scorer.record_execution(cid, latency_ms=80.0, cost_usd=0.0, success=True, quality_rating=0.90)
    scorer.record_execution(cid, latency_ms=90.0, cost_usd=0.0, success=True, quality_rating=0.92)

    task = TaskProfile(task_id="t3", task_type=TaskType.FAST_QUERY)
    score = scorer.score_model(fast_model, task)

    assert score.estimated_latency_ms < 100.0


def test_scorer_tool_candidate():
    scorer = TelemetryScorer()
    tool = ToolCandidate(
        tool_id="calculator",
        name="Precise Math Calculator",
        avg_latency_ms=15.0,
        error_rate=0.001,
        token_overhead=50,
        capabilities=["math"],
    )
    task = TaskProfile(task_id="t4", task_type=TaskType.TOOL_USE, required_capabilities=["math"])

    score = scorer.score_tool(tool, task)
    assert score.candidate_id == "calculator"
    assert score.composite_score > 0.85
    assert score.estimated_latency_ms == 15.0
