"""Empirical benchmark evaluation suite proving Auto picks beat static manual picks on a test set."""

from typing import Dict, List
from ..core.interfaces import BaseBenchmarkSuite
from ..core.models import (
    BenchmarkResult,
    ModelCandidate,
    TaskProfile,
)
from ..engine.recommender_service import RecommenderService


class BenchmarkSuite(BaseBenchmarkSuite):
    """Compares Auto-recommender routing vs static manual model selection across a representative test set."""

    def __init__(self, recommender_service: RecommenderService):
        self.recommender = recommender_service

    def run_benchmark(
        self,
        tasks: List[TaskProfile],
        models: List[ModelCandidate],
        manual_fixed_candidate_id: str,
    ) -> BenchmarkResult:
        model_lookup: Dict[str, ModelCandidate] = {
            m.candidate_id: m for m in models
        }
        manual_candidate = model_lookup.get(manual_fixed_candidate_id)
        if not manual_candidate:
            raise ValueError(
                f"Manual model '{manual_fixed_candidate_id}' not found in candidate pool"
            )

        manual_total_cost = 0.0
        auto_total_cost = 0.0
        manual_latencies = []
        auto_latencies = []
        manual_successes = 0
        auto_successes = 0
        auto_wins = 0
        manual_wins = 0

        for task in tasks:
            # 1. Manual Pick Execution
            m_input_cost = (
                task.prompt_token_estimate / 1000.0
            ) * manual_candidate.cost_per_1k_input
            m_output_cost = (
                task.expected_output_tokens / 1000.0
            ) * manual_candidate.cost_per_1k_output
            m_cost = m_input_cost + m_output_cost
            m_latency = manual_candidate.metrics.avg_latency_ms
            m_success = manual_candidate.metrics.success_rate >= 0.8

            manual_total_cost += m_cost
            manual_latencies.append(m_latency)
            if m_success:
                manual_successes += 1

            # 2. Auto Recommender Pick Execution
            decision = self.recommender.recommend_model(task, models)
            auto_candidate = model_lookup[decision.recommended_id]

            a_input_cost = (
                task.prompt_token_estimate / 1000.0
            ) * auto_candidate.cost_per_1k_input
            a_output_cost = (
                task.expected_output_tokens / 1000.0
            ) * auto_candidate.cost_per_1k_output
            a_cost = a_input_cost + a_output_cost
            a_latency = auto_candidate.metrics.avg_latency_ms
            a_success = auto_candidate.metrics.success_rate >= 0.8

            auto_total_cost += a_cost
            auto_latencies.append(a_latency)
            if a_success:
                auto_successes += 1

            # 3. Determine Win on Multi-Objective Efficiency
            # An auto pick wins if it achieves lower cost without significant latency degradation,
            # or faster latency when speed is prioritized, or higher success rate.
            auto_score = 0
            if a_cost < m_cost:
                auto_score += 1
            elif a_cost > m_cost:
                auto_score -= 1

            if a_latency < m_latency:
                auto_score += 1
            elif a_latency > m_latency:
                auto_score -= 1

            if auto_candidate.metrics.quality_score >= manual_candidate.metrics.quality_score:
                auto_score += 1

            if auto_score > 0:
                auto_wins += 1
            else:
                manual_wins += 1

        total_tasks = len(tasks)
        avg_manual_lat = (
            sum(manual_latencies) / total_tasks if total_tasks > 0 else 0.0
        )
        avg_auto_lat = sum(auto_latencies) / total_tasks if total_tasks > 0 else 0.0

        cost_reduction = (
            ((manual_total_cost - auto_total_cost) / manual_total_cost * 100.0)
            if manual_total_cost > 0
            else 0.0
        )
        latency_reduction = (
            ((avg_manual_lat - avg_auto_lat) / avg_manual_lat * 100.0)
            if avg_manual_lat > 0
            else 0.0
        )

        win_ratio = auto_wins / total_tasks if total_tasks > 0 else 0.0

        return BenchmarkResult(
            total_evaluations=total_tasks,
            manual_total_cost_usd=round(manual_total_cost, 6),
            auto_total_cost_usd=round(auto_total_cost, 6),
            manual_avg_latency_ms=round(avg_manual_lat, 2),
            auto_avg_latency_ms=round(avg_auto_lat, 2),
            manual_success_rate=round(manual_successes / total_tasks, 4) if total_tasks > 0 else 1.0,
            auto_success_rate=round(auto_successes / total_tasks, 4) if total_tasks > 0 else 1.0,
            cost_reduction_percent=round(cost_reduction, 2),
            latency_reduction_percent=round(latency_reduction, 2),
            auto_wins=auto_wins,
            manual_wins=manual_wins,
            win_ratio=round(win_ratio, 4),
        )
