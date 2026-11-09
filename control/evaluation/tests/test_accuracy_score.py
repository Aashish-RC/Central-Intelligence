"""Tests for Crown Jewel: Accuracy Score Evaluator (Task 11.7, Feature 11.14)."""

import pytest
from control.evaluation.accuracy.composite_score import AccuracyScoreEvaluator
from control.evaluation.accuracy.thresholds import ThresholdAction


def test_accuracy_score_evaluator_high_quality_deliver():
    """Acceptance Test: High-quality response (all claims verified, positive feedback) -> score >= 0.80 -> 'deliver'."""
    evaluator = AccuracyScoreEvaluator()

    response = "The capital of France is Paris. The Eiffel Tower was completed in 1889."
    reference = [
        "The capital of France is Paris and it is known for European culture.",
        "The Eiffel Tower was completed in 1889 for the World's Fair.",
    ]
    candidates = [
        response,
        "Paris is France's capital. The Eiffel Tower was built in 1889.",
    ]

    result = evaluator.evaluate_response(
        response_text=response,
        reference_knowledge=reference,
        candidate_predictions=candidates,
        explicit_feedback_score=0.95,
        stated_confidence=0.95,
    )

    assert result.composite >= 0.80
    assert result.threshold_action == ThresholdAction.DELIVER
    assert result.feedback >= 0.90
    assert result.web >= 0.90
    assert result.consensus >= 0.60
    assert "Action: deliver" in result.explanation


def test_accuracy_score_evaluator_medium_flag_low_confidence():
    """Acceptance Test: Medium response (some claims unverified) -> 0.50 <= S < 0.80 -> 'flag_low_confidence'."""
    evaluator = AccuracyScoreEvaluator()

    response = "Water boils at 100 degrees Celsius. Gold melts at 50 degrees."
    # Reference only supports water boiling, not gold melting at 50 degrees
    reference = ["Water boils at 100 degrees Celsius at sea level."]

    result = evaluator.evaluate_response(
        response_text=response,
        reference_knowledge=reference,
        candidate_predictions=None,  # Neutral consensus (0.50)
        explicit_feedback_score=0.60,
    )

    assert 0.50 <= result.composite < 0.80
    assert result.threshold_action == ThresholdAction.FLAG_LOW_CONFIDENCE
    assert "Action: flag_low_confidence" in result.explanation


def test_accuracy_score_evaluator_low_trigger_second_opinion_def03():
    """Acceptance Test: Low-quality response (unverified, negative feedback) -> S < 0.50 -> 'trigger_second_opinion'."""
    evaluator = AccuracyScoreEvaluator()

    response = "Jupiter is made entirely of solid diamond. The sun revolves around Mars."
    reference = ["Jupiter is a gas giant primarily composed of hydrogen and helium."]

    result = evaluator.evaluate_response(
        response_text=response,
        reference_knowledge=reference,
        candidate_predictions=[
            "Jupiter is a gas giant with no solid surface.",
            "Mars revolves around the sun, which is a star.",
        ],
        explicit_feedback_score=0.10,
    )

    assert result.composite < 0.50
    assert result.threshold_action == ThresholdAction.TRIGGER_SECOND_OPINION
    assert "Action: trigger_second_opinion" in result.explanation
    # This action directly gates L8 Second-Opinion Trigger (DEF-03 unblock)
