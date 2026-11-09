"""Tests for Accuracy Thresholds and Transparency (Task 11.9, Features 11.16, 11.17)."""

import pytest
from control.evaluation.accuracy.thresholds import (
    AccuracyThresholdConfig,
    ThresholdAction,
)


def test_configurable_thresholds():
    """Validates custom configurable threshold boundaries."""
    # Custom stricter policy: deliver only at 0.90, second opinion at 0.70
    custom_config = AccuracyThresholdConfig(
        deliver_threshold=0.90,
        second_opinion_threshold=0.70,
        user_visibility_enabled=True,
    )

    assert custom_config.evaluate_action(0.92) == ThresholdAction.DELIVER
    assert custom_config.evaluate_action(0.85) == ThresholdAction.FLAG_LOW_CONFIDENCE
    assert custom_config.evaluate_action(0.65) == ThresholdAction.TRIGGER_SECOND_OPINION
    assert custom_config.user_visibility_enabled is True
