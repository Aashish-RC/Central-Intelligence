"""Tests for Confidence Calibration (Task 11.8, Feature 11.15)."""

import pytest
from control.evaluation.accuracy.calibration import ConfidenceCalibrator


def test_confidence_calibration_well_calibrated():
    """Validates calibration curve calculation for well-calibrated predictions."""
    calibrator = ConfidenceCalibrator(num_bins=5, ece_threshold=0.15)

    # In 0.8-1.0 bin, 90% correct
    for _ in range(9):
        calibrator.record_prediction(0.90, actual_outcome=True)
    calibrator.record_prediction(0.90, actual_outcome=False)

    # In 0.2-0.4 bin, 30% correct
    for _ in range(3):
        calibrator.record_prediction(0.30, actual_outcome=True)
    for _ in range(7):
        calibrator.record_prediction(0.30, actual_outcome=False)

    report = calibrator.calculate_calibration()
    assert report.total_samples == 20
    assert report.expected_calibration_error <= 0.15
    assert report.well_calibrated is True
    assert len(report.bins) == 5


def test_confidence_calibration_poorly_calibrated():
    """Validates that high confidence with low accuracy triggers calibration error."""
    calibrator = ConfidenceCalibrator(num_bins=5, ece_threshold=0.10)

    # Overconfident: stated 95% confidence, but actually failed 100% of the time
    for _ in range(10):
        calibrator.record_prediction(0.95, actual_outcome=False)

    report = calibrator.calculate_calibration()
    assert report.expected_calibration_error >= 0.80
    assert report.well_calibrated is False

