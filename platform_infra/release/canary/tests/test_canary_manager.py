"""Tests for L17 Canary Deployment Controller."""

from platform_infra.release.canary.canary_manager import (
    CanaryDeploymentManager,
    CanaryState,
)
from platform_infra.release.gates.release_gate import GateStatus


def test_canary_rollout_5_to_100_percent():
    mgr = CanaryDeploymentManager()
    baseline = {"pass_rate": 0.92, "hallucination_rate": 0.01, "sample_size": 50}
    rollout = mgr.start_canary("rel-2.1", "feat_new_planner", initial_percentage=5.0, baseline_metrics=baseline)
    assert rollout.percentage == 5.0

    # Check user sampling reflects small canary (~5% out of 200 users)
    sampled = sum(1 for i in range(200) if mgr.evaluate_user("rel-2.1", f"user_{i}"))
    assert 0 < sampled < 30

    step = mgr.advance_canary(
        "rel-2.1",
        candidate_metrics={"pass_rate": 0.94, "hallucination_rate": 0.01, "sample_size": 40},
        target_percentage=100.0,
    )
    assert step.state == CanaryState.COMPLETED
    assert step.gate_status == GateStatus.APPROVED
    assert step.percentage == 100.0
    assert mgr.evaluate_user("rel-2.1", "user_1") is True


def test_canary_auto_rollback_on_gate_failure():
    mgr = CanaryDeploymentManager()
    baseline = {"pass_rate": 0.95, "hallucination_rate": 0.01, "sample_size": 50}
    mgr.start_canary("rel-bad", "feat_bad", initial_percentage=5.0, baseline_metrics=baseline)

    step = mgr.advance_canary(
        "rel-bad",
        candidate_metrics={"pass_rate": 0.60, "hallucination_rate": 0.15, "sample_size": 30},
        target_percentage=50.0,
    )
    assert step.state == CanaryState.ROLLED_BACK
    assert step.gate_status == GateStatus.BLOCKED
    assert step.percentage == 0.0
    assert mgr.evaluate_user("rel-bad", "user_42") is False

