"""Tests for RecommenderService."""

import pytest
from recommender.core.models import (
    CandidateMetrics,
    ModelCandidate,
    OptimizationGoal,
    TaskProfile,
    TaskType,
    ToolCandidate,
)
from recommender.engine.recommender_service import RecommenderService


@pytest.fixture
def candidate_models():
    return [
        ModelCandidate(
            provider="ollama",
            model_name="mistral-7b",
            capabilities=["chat"],
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            metrics=CandidateMetrics(avg_latency_ms=100.0, quality_score=0.75),
        ),
        ModelCandidate(
            provider="openai",
            model_name="gpt-4o",
            capabilities=["reasoning", "coding", "vision"],
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
            metrics=CandidateMetrics(avg_latency_ms=650.0, quality_score=0.95),
        ),
        ModelCandidate(
            provider="gemini",
            model_name="gemini-1.5-flash",
            capabilities=["fast", "coding", "chat"],
            cost_per_1k_input=0.0003,
            cost_per_1k_output=0.001,
            metrics=CandidateMetrics(avg_latency_ms=250.0, quality_score=0.88),
        ),
    ]


def test_recommend_model_budget_task(candidate_models):
    service = RecommenderService()
    task = TaskProfile(
        task_id="task_cheap",
        task_type=TaskType.FAST_QUERY,
        goal=OptimizationGoal.MIN_COST,
    )

    decision = service.recommend_model(task, candidate_models)
    assert decision.recommended_id == "ollama/mistral-7b"
    assert "optimal fit for fast_query" in decision.one_line_reason
    assert decision.candidate_type == "model"
    assert decision.composite_score > 0.0


def test_recommend_model_quality_task(candidate_models):
    service = RecommenderService()
    task = TaskProfile(
        task_id="task_deep",
        task_type=TaskType.REASONING,
        goal=OptimizationGoal.MAX_QUALITY,
        required_capabilities=["reasoning", "coding"],
    )

    decision = service.recommend_model(task, candidate_models)
    assert decision.recommended_id == "openai/gpt-4o"
    assert decision.runner_up_id is not None
    assert decision.confidence_margin > 0.0


def test_recommend_tool():
    service = RecommenderService()
    tools = [
        ToolCandidate(tool_id="grep_search", name="Grep", avg_latency_ms=10.0, capabilities=["search"]),
        ToolCandidate(tool_id="full_crawl", name="Crawler", avg_latency_ms=2500.0, capabilities=["scrape"]),
    ]
    task = TaskProfile(task_id="t_tool", task_type=TaskType.TOOL_USE, required_capabilities=["search"])

    decision = service.recommend_tool(task, tools)
    assert decision.recommended_id == "grep_search"
    assert decision.candidate_type == "tool"
    assert "matched tool_use requirements" in decision.one_line_reason
