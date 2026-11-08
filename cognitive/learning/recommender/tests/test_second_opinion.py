"""Tests for SecondOpinionArbiter."""

import pytest
from recommender.core.models import (
    CandidateScore,
    RiskLevel,
    TaskProfile,
    TaskType,
)
from recommender.engine.second_opinion import SecondOpinionArbiter


@pytest.fixture
def arbiter():
    return SecondOpinionArbiter(confidence_threshold=0.04)


def test_second_opinion_trigger_on_high_risk(arbiter):
    task = TaskProfile(task_id="tx1", risk_level=RiskLevel.HIGH)
    top = CandidateScore(
        candidate_id="model_a",
        cost_score=0.9,
        latency_score=0.9,
        quality_score=0.85,
        reliability_score=0.88,
        composite_score=0.88,
        estimated_cost_usd=0.001,
        estimated_latency_ms=200.0,
    )
    runner = CandidateScore(
        candidate_id="model_b",
        cost_score=0.7,
        latency_score=0.7,
        quality_score=0.95,
        reliability_score=0.99,
        composite_score=0.80,
        estimated_cost_usd=0.005,
        estimated_latency_ms=500.0,
    )

    # High risk task triggers second opinion
    should_trigger = arbiter.should_trigger_second_opinion(top, runner, task)
    assert should_trigger is True

    # Arbitration switches to model_b due to superior reliability on high risk
    chosen_id, reason = arbiter.arbitrate(top, runner, task)
    assert chosen_id == "model_b"
    assert "superior reliability" in reason


def test_second_opinion_trigger_on_narrow_margin(arbiter):
    task = TaskProfile(task_id="tx2", risk_level=RiskLevel.LOW)
    top = CandidateScore(
        candidate_id="model_x",
        cost_score=0.85,
        latency_score=0.80,
        quality_score=0.85,
        reliability_score=0.95,
        composite_score=0.850,
        estimated_cost_usd=0.002,
        estimated_latency_ms=800.0,
    )
    runner = CandidateScore(
        candidate_id="model_y",
        cost_score=0.86,
        latency_score=0.95,
        quality_score=0.82,
        reliability_score=0.95,
        composite_score=0.835,  # within delta of 0.015 (< 0.04)
        estimated_cost_usd=0.002,
        estimated_latency_ms=250.0,  # much faster
    )

    should_trigger = arbiter.should_trigger_second_opinion(top, runner, task)
    assert should_trigger is True

    # Runner-up offers 40%+ faster latency within marginal delta
    chosen_id, reason = arbiter.arbitrate(top, runner, task)
    assert chosen_id == "model_y"
    assert "faster latency" in reason


def test_second_opinion_clear_lead_no_trigger(arbiter):
    task = TaskProfile(task_id="tx3", risk_level=RiskLevel.LOW)
    top = CandidateScore(
        candidate_id="model_top",
        cost_score=0.9,
        latency_score=0.9,
        quality_score=0.9,
        reliability_score=0.98,
        composite_score=0.92,
        estimated_cost_usd=0.001,
        estimated_latency_ms=200.0,
    )
    runner = CandidateScore(
        candidate_id="model_runner",
        cost_score=0.6,
        latency_score=0.6,
        quality_score=0.7,
        reliability_score=0.90,
        composite_score=0.70,  # delta = 0.22 >> 0.04
        estimated_cost_usd=0.004,
        estimated_latency_ms=600.0,
    )

    should_trigger = arbiter.should_trigger_second_opinion(top, runner, task)
    assert should_trigger is False
