"""Unit tests for PlatformReleaseGate tied to L11 (Task 17.6)."""

import pytest
from platform_infra.release.gates.release_gate import (
    PlatformReleaseGate,
    GateStatus,
)


@pytest.fixture
def gate():
    return PlatformReleaseGate(max_allowed_regression=0.05, min_pass_rate=0.85)


def test_ten_percent_quality_regression_is_blocked(gate: PlatformReleaseGate):
    """Acceptance test: Release with 10% quality regression is blocked."""
    baseline = {
        "accuracy_score": 0.95,
        "pass_rate": 0.96,
        "hallucination_rate": 0.02,
        "sample_size": 100,
    }
    # 10% quality drop (accuracy down from 0.95 to 0.85)
    candidate_regressed = {
        "accuracy_score": 0.85,
        "pass_rate": 0.86,
        "hallucination_rate": 0.03,
        "sample_size": 100,
    }

    decision = gate.evaluate_release(
        release_id="rel_candidate_v2.6.0_rc1",
        candidate_metrics=candidate_regressed,
        baseline_metrics=baseline,
    )

    assert decision.passed is False
    assert decision.status == GateStatus.BLOCKED
    assert any("Accuracy regression of 0.1000" in r for r in decision.reasons)


def test_high_quality_candidate_is_approved(gate: PlatformReleaseGate):
    """Candidate that maintains or improves accuracy is approved."""
    baseline = {
        "accuracy_score": 0.90,
        "pass_rate": 0.91,
        "hallucination_rate": 0.03,
        "sample_size": 50,
    }
    candidate_improved = {
        "accuracy_score": 0.93,
        "pass_rate": 0.94,
        "hallucination_rate": 0.02,
        "sample_size": 50,
    }

    decision = gate.evaluate_release(
        release_id="rel_candidate_v2.6.0_rc2",
        candidate_metrics=candidate_improved,
        baseline_metrics=baseline,
    )

    assert decision.passed is True
    assert decision.status == GateStatus.APPROVED
    assert len(decision.reasons) == 0


def test_hallucination_spike_is_blocked(gate: PlatformReleaseGate):
    """Candidate with unacceptable hallucination rate is blocked."""
    candidate_hallucinating = {
        "accuracy_score": 0.92,
        "pass_rate": 0.90,
        "hallucination_rate": 0.12,  # 12% hallucination rate exceeds 5% max
        "sample_size": 50,
    }

    decision = gate.evaluate_release(
        release_id="rel_candidate_v2.6.0_rc3",
        candidate_metrics=candidate_hallucinating,
    )

    assert decision.passed is False
    assert decision.status == GateStatus.BLOCKED
    assert any("Hallucination rate 12.00% exceeds maximum" in r for r in decision.reasons)

