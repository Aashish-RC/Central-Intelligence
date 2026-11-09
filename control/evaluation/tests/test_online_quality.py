"""Tests for Online Quality Monitoring Modules (Task 11.6)."""

import pytest
from control.evaluation.online.auto_judge import AutoJudge
from control.evaluation.online.bias_fairness import BiasFairnessMonitor
from control.evaluation.online.dashboard import OnlineQualityMonitor
from control.evaluation.online.drift_detector import OnlineDriftDetector
from control.evaluation.online.failure_clusterer import FailureClusterer
from control.evaluation.online.hallucination_tracker import HallucinationTracker
from control.evaluation.online.human_review import HumanReviewQueue, ReviewStatus
from control.evaluation.online.quality_bar import QualityBarManager
from control.evaluation.online.satisfaction import SatisfactionTracker


def test_auto_judge():
    judge = AutoJudge(pass_threshold=0.6)
    res = judge.evaluate(
        trace_id="t-1",
        query="What is quantum computing?",
        response="Quantum computing leverages qubits and superposition to process data.",
        context="Quantum computing uses qubits.",
    )
    assert res.passed is True
    assert res.overall_score >= 0.6
    assert len(res.scores) == 3


def test_human_review_queue():
    queue = HumanReviewQueue(random_sample_rate=0.0, low_confidence_threshold=0.5)

    # High confidence -> not sampled
    item1 = queue.maybe_sample("t-high", "hello", "hi", confidence_score=0.95)
    assert item1 is None

    # Low confidence -> sampled
    item2 = queue.maybe_sample("t-low", "what?", "dunno", confidence_score=0.35)
    assert item2 is not None
    assert item2.sampling_reason == "low_confidence"
    assert len(queue.get_pending_reviews()) == 1

    # Submit review
    reviewed = queue.submit_review(
        item_id=item2.item_id,
        status=ReviewStatus.EDITED,
        reviewer_id="human_01",
        feedback="Incomplete response",
        corrected_response="Here is the complete information.",
    )
    assert reviewed.status == ReviewStatus.EDITED
    assert reviewed.reviewer_id == "human_01"


def test_failure_clusterer():
    clusterer = FailureClusterer()
    clusterer.record_failure("inc-1", "Gateway timeout after 30s")
    clusterer.record_failure("inc-2", "Request deadline exceeded")
    clusterer.record_failure("inc-3", "Invalid JSON syntax parsed from tool")

    clusters = clusterer.get_clusters()
    assert len(clusters) == 2
    assert clusters[0].category == "timeout_exhaustion"
    assert clusters[0].count == 2
    assert clusters[1].category == "schema_parsing_error"


def test_quality_bar_manager():
    mgr = QualityBarManager(tenant_overrides={"enterprise_tenant": {"finance": 0.99}})
    # Default finance
    assert mgr.check(0.96, domain="finance", tenant_id="default").meets_bar is True
    # Enterprise finance override requires 0.99
    assert mgr.check(0.96, domain="finance", tenant_id="enterprise_tenant").meets_bar is False


def test_online_quality_dashboard_acceptance():
    """Acceptance Test: Live dashboard shows hallucination rate, drift, bias, satisfaction trends."""
    monitor = OnlineQualityMonitor()

    # 1. Hallucination tracking
    monitor.hallucination_tracker.record_check(is_hallucinated=False)
    monitor.hallucination_tracker.record_check(is_hallucinated=False)
    monitor.hallucination_tracker.record_check(is_hallucinated=True)

    # 2. Drift detection
    monitor.drift_detector.set_baseline([10.0] * 20)
    for _ in range(50):
        monitor.drift_detector.record_observation(15.0)

    # 3. Bias & Fairness
    monitor.bias_monitor.record_outcome("cohort_A", 0.92)
    monitor.bias_monitor.record_outcome("cohort_B", 0.88)

    # 4. Satisfaction trends
    monitor.satisfaction_tracker.record_feedback("fb-1", "u1", "t1", rating=5)
    monitor.satisfaction_tracker.record_feedback("fb-2", "u2", "t2", rating=4)
    monitor.satisfaction_tracker.record_feedback("fb-3", "u3", "t3", rating=5)
    monitor.satisfaction_tracker.record_feedback("fb-4", "u4", "t4", rating=5)

    snapshot = monitor.get_dashboard_snapshot()

    # Verify hallucination rate
    assert snapshot.hallucination.total_evaluated == 3
    assert snapshot.hallucination.hallucination_count == 1
    assert 0.33 <= snapshot.hallucination.hallucination_rate <= 0.34

    # Verify drift
    assert snapshot.drift.is_drifted is True
    assert snapshot.drift.drift_score > 0.4

    # Verify bias/fairness
    assert snapshot.bias_fairness.is_fair is True
    assert snapshot.bias_fairness.parity_gap <= 0.05

    # Verify satisfaction trends
    assert snapshot.satisfaction.total_feedbacks == 4
    assert snapshot.satisfaction.csat_score == 1.0
    assert snapshot.satisfaction.average_rating >= 4.5

