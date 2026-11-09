"""Tests for Experiments, A/B Testing, and Release Quality Gates (Task 11.10)."""

import pytest
from control.evaluation.experiments.model_ab_test import ModelABTestHarness
from control.evaluation.experiments.prompt_ab_test import PromptABTestRunner
from control.evaluation.experiments.release_gates import (
    QualityGatePolicy,
    ReleaseGateEvaluator,
)
from control.evaluation.experiments.routing_ab_test import RoutingABTestRunner
from control.evaluation.experiments.shadow_canary import (
    CanaryEvaluator,
    ShadowTrafficEvaluator,
)
from control.evaluation.experiments.side_by_side import (
    SideBySideEvaluator,
    SideBySideVerdict,
)
from control.evaluation.experiments.significance import calculate_significance


def test_ab_test_and_release_gates_acceptance():
    """Acceptance Test: Run A/B test between Claude and GPT-4; results show statistical significance; release gate blocks if quality regresses."""
    harness = ModelABTestHarness(
        experiment_id="exp-claude-vs-gpt4",
        model_a="claude-3-7-sonnet",
        model_b="gpt-4o",
    )

    # Simulate 50 runs for Claude (high quality ~0.94)
    for i in range(50):
        harness.record_run(
            sample_id=f"c-{i}",
            model_name="claude-3-7-sonnet",
            quality_score=0.92 + (0.01 * (i % 5)),
            latency_ms=450.0,
        )

    # Simulate 50 runs for GPT-4 (significantly lower score for test ~0.75)
    for i in range(50):
        harness.record_run(
            sample_id=f"g-{i}",
            model_name="gpt-4o",
            quality_score=0.74 + (0.01 * (i % 4)),
            latency_ms=520.0,
        )

    report = harness.evaluate_experiment()
    assert report.observations_a == 50
    assert report.observations_b == 50
    assert report.significance.is_significant is True
    assert report.significance.p_value < 0.01
    assert report.winner == "claude-3-7-sonnet"

    # Release gate test: Candidate with quality regression gets blocked
    gate = ReleaseGateEvaluator(
        policy=QualityGatePolicy(
            min_pass_rate=0.90,
            max_accuracy_regression=0.03,
            min_sample_size=30,
        )
    )

    baseline_metrics = {"accuracy_score": 0.94, "pass_rate": 0.96}
    # Candidate metrics regressed to 0.75
    regressed_candidate = {
        "accuracy_score": 0.75,
        "pass_rate": 0.78,
        "sample_size": 50,
        "hallucination_rate": 0.08,
    }

    gate_result = gate.evaluate(candidate_metrics=regressed_candidate, baseline_metrics=baseline_metrics)
    assert gate_result.passed is False
    assert any("regression" in r.lower() for r in gate_result.reasons)
    assert any("pass rate" in r.lower() for r in gate_result.reasons)

    # Valid candidate passes
    valid_candidate = {
        "accuracy_score": 0.95,
        "pass_rate": 0.98,
        "sample_size": 50,
        "hallucination_rate": 0.01,
    }
    assert gate.evaluate(candidate_metrics=valid_candidate, baseline_metrics=baseline_metrics).passed is True


def test_shadow_and_canary_evaluator():
    """Validates shadow traffic collection and canary rollback trigger."""
    # Shadow evaluation
    shadow = ShadowTrafficEvaluator()
    shadow.record_shadow_run(
        trace_id="tr-1",
        prod_resp="Prod text",
        shadow_resp="Shadow text",
        prod_score=0.90,
        shadow_score=0.92,
        shadow_latency_ms=300.0,
    )
    metrics = shadow.get_aggregate_metrics()
    assert metrics["total"] == 1
    assert metrics["shadow_parity"] > 1.0

    # Canary evaluator
    canary = CanaryEvaluator(canary_percentage=0.10, max_error_rate=0.05, max_score_drop=0.05)
    # Healthy canary
    for _ in range(20):
        canary.record_canary_request(score=0.91, is_error=False)
    assert canary.evaluate_health(baseline_quality_score=0.90).should_rollback is False

    # Broken canary with errors
    broken_canary = CanaryEvaluator(canary_percentage=0.10, max_error_rate=0.05)
    for _ in range(15):
        broken_canary.record_canary_request(score=0.50, is_error=True)
    report = broken_canary.evaluate_health(baseline_quality_score=0.90)
    assert report.should_rollback is True
    assert "error rate" in report.reason.lower()


def test_side_by_side_and_variants():
    """Validates blind side-by-side preference evaluation."""
    sbs = SideBySideEvaluator("modelA", "modelB")
    sbs.record_judgment("prompt 1", "out A", "out B", SideBySideVerdict.MODEL_A_WINS)
    sbs.record_judgment("prompt 2", "out A", "out B", SideBySideVerdict.MODEL_A_WINS)
    sbs.record_judgment("prompt 3", "out A", "out B", SideBySideVerdict.MODEL_B_WINS)

    rates = sbs.get_win_rates()
    assert rates["modelA"] == pytest.approx(0.6667, rel=1e-2)
    assert rates["modelB"] == pytest.approx(0.3333, rel=1e-2)

