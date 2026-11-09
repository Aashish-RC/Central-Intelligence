"""Tests for Unified End-to-End Pipeline Runner (Task 11.5)."""

import pytest
from control.evaluation.e2e.test_runner import (
    E2EPipelineRun,
    PipelineStage,
    UnifiedE2ETestRunner,
)


def test_unified_e2e_pipeline_full_sequence_acceptance():
    """Acceptance Test: E2E test exercises all Central-Intelligence layers in sequence."""
    runner = UnifiedE2ETestRunner()

    initial_request = {
        "user_id": "test_user_007",
        "query": "Generate architectural summary for Project Apollo",
    }

    report: E2EPipelineRun = runner.execute_pipeline(initial_request)

    assert report.overall_success is True
    assert len(report.stages) == 7

    # Verify all layers executed in correct dependency sequence
    expected_order = [
        PipelineStage.L1_GATEWAY,
        PipelineStage.L2_MEMORY,
        PipelineStage.L3_KNOWLEDGE,
        PipelineStage.L4_REASONING,
        PipelineStage.L5_ACTION,
        PipelineStage.L6_COLLABORATION,
        PipelineStage.L8_ORCHESTRATION,
    ]
    for idx, expected_stage in enumerate(expected_order):
        assert report.stages[idx].stage == expected_stage
        assert report.stages[idx].success is True
        assert report.stages[idx].duration_ms >= 0.0

    # Verify final response propagated from L8
    l8_res = report.get_stage_result(PipelineStage.L8_ORCHESTRATION)
    assert l8_res is not None
    assert "routed_model" in l8_res.output_payload


def test_unified_e2e_pipeline_stage_interruption():
    """Verifies that failure in a stage halts subsequent pipeline execution cleanly."""
    runner = UnifiedE2ETestRunner()

    def failing_action(payload):
        raise RuntimeError("Sandbox resource limit exceeded in L5")

    runner.register_stage(PipelineStage.L5_ACTION, failing_action)

    report = runner.execute_pipeline({"user_id": "user_fail"})

    assert report.overall_success is False
    assert len(report.stages) == 5  # L1, L2, L3, L4 succeed, L5 fails, L6 & L8 not executed
    assert report.stages[4].stage == PipelineStage.L5_ACTION
    assert report.stages[4].success is False
    assert "Sandbox resource limit" in str(report.stages[4].error)
