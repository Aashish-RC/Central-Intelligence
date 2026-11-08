"""Tests for BenchmarkSuite: Verifies that Auto picks beat manual picks on a test set."""

import pytest
from recommender.core.models import (
    CandidateMetrics,
    ModelCandidate,
    OptimizationGoal,
    RiskLevel,
    TaskProfile,
    TaskType,
)
from recommender.engine.recommender_service import RecommenderService
from recommender.eval.benchmark_suite import BenchmarkSuite


@pytest.fixture
def benchmark_model_pool():
    return [
        # Heavy static default (e.g. expensive flagship)
        ModelCandidate(
            provider="openai",
            model_name="gpt-4-expensive",
            capabilities=["reasoning", "coding", "fast", "chat"],
            cost_per_1k_input=0.010,
            cost_per_1k_output=0.030,
            metrics=CandidateMetrics(avg_latency_ms=1200.0, quality_score=0.96),
        ),
        # Mid-tier balanced model
        ModelCandidate(
            provider="anthropic",
            model_name="claude-3-5-sonnet",
            capabilities=["reasoning", "coding", "chat"],
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            metrics=CandidateMetrics(avg_latency_ms=650.0, quality_score=0.95),
        ),
        # Ultra fast & cheap model
        ModelCandidate(
            provider="gemini",
            model_name="gemini-flash",
            capabilities=["fast", "chat"],
            cost_per_1k_input=0.0003,
            cost_per_1k_output=0.001,
            metrics=CandidateMetrics(avg_latency_ms=180.0, quality_score=0.88),
        ),
        # Local zero-cost model
        ModelCandidate(
            provider="ollama",
            model_name="llama-3-8b",
            capabilities=["chat", "fast"],
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            metrics=CandidateMetrics(avg_latency_ms=95.0, quality_score=0.82),
        ),
    ]


@pytest.fixture
def workload_tasks():
    return [
        TaskProfile(
            task_id="task_1_simple_ping",
            task_type=TaskType.FAST_QUERY,
            goal=OptimizationGoal.MIN_COST,
            prompt_token_estimate=50,
            expected_output_tokens=50,
        ),
        TaskProfile(
            task_id="task_2_quick_classification",
            task_type=TaskType.FAST_QUERY,
            goal=OptimizationGoal.MIN_LATENCY,
            prompt_token_estimate=120,
            expected_output_tokens=30,
        ),
        TaskProfile(
            task_id="task_3_deep_reasoning",
            task_type=TaskType.REASONING,
            goal=OptimizationGoal.MAX_QUALITY,
            risk_level=RiskLevel.HIGH,
            required_capabilities=["reasoning"],
            prompt_token_estimate=800,
            expected_output_tokens=600,
        ),
        TaskProfile(
            task_id="task_4_balanced_summarization",
            task_type=TaskType.FAST_QUERY,
            goal=OptimizationGoal.BALANCED,
            prompt_token_estimate=400,
            expected_output_tokens=150,
        ),
        TaskProfile(
            task_id="task_5_budget_extraction",
            task_type=TaskType.FAST_QUERY,
            goal=OptimizationGoal.MIN_COST,
            prompt_token_estimate=250,
            expected_output_tokens=100,
        ),
    ]


def test_auto_picks_beat_manual_picks_on_benchmark(benchmark_model_pool, workload_tasks):
    service = RecommenderService()
    suite = BenchmarkSuite(service)

    # Static manual strategy: Naively uses expensive "openai/gpt-4-expensive" for everything
    manual_candidate_id = "openai/gpt-4-expensive"

    result = suite.run_benchmark(
        tasks=workload_tasks,
        models=benchmark_model_pool,
        manual_fixed_candidate_id=manual_candidate_id,
    )

    # Core spec assertion: "Auto picks beat manual picks on a test set"
    assert result.auto_wins > result.manual_wins
    assert result.win_ratio >= 0.70  # At least 70% win rate
    assert result.auto_total_cost_usd < result.manual_total_cost_usd
    assert result.cost_reduction_percent > 40.0  # Over 40% cost reduction
    assert result.auto_avg_latency_ms < result.manual_avg_latency_ms
    assert result.latency_reduction_percent > 30.0  # Over 30% latency reduction
    assert result.auto_success_rate == 1.0
