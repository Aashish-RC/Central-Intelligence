"""
Unit tests for Metric Anomaly Detector (14.14).
"""

import time
import pytest
from control.observability.alerts.anomaly_detector import AnomalyDetector, AnomalyAlert
from control.observability.signoz.signoz_adapter import SigNozAdapter


def test_normal_metric_no_alert():
    """Verify standard metric fluctuations within normal distribution do not alert."""
    detector = AnomalyDetector(baseline_window=3600, sigma_threshold=3.0)

    # Historical values: latency around 100ms with small variance (std ~ 5)
    historical_latencies = [98.0, 102.0, 99.0, 101.0, 100.0, 97.0, 103.0, 100.0]
    normal_val = 105.0  # z-score ~ (105 - 100) / 2 = ~2.5, below 3.0

    alert = detector.detect("api.request.latency_ms", normal_val, historical_latencies)
    assert alert is None


def test_latency_spike_greater_than_3_sigma_triggers_alert():
    """Acceptance: Latency spike >3σ triggers alert immediately."""
    detector = AnomalyDetector(baseline_window=3600, sigma_threshold=3.0)

    dispatched = []
    detector.add_handler(lambda a: dispatched.append(a))
    detector.add_webhook_sink("https://alerts.internal/webhook")
    detector.add_slack_sink("#sre-incidents")
    detector.add_email_sink("oncall@centralintelligence.org")

    historical_latencies = [100.0, 102.0, 98.0, 101.0, 99.0, 100.0] * 10
    spike_val = 350.0  # Latency spikes to 350ms (mean=100, std~1.2, z > 100)

    alert = detector.detect("llm.latency_ms", spike_val, historical_latencies)
    assert alert is not None
    assert alert.metric == "llm.latency_ms"
    assert alert.value == 350.0
    assert alert.expected == pytest.approx(100.0, rel=1e-2)
    assert alert.z_score > 3.0
    assert alert.severity in ("high", "critical")

    # Now test streaming feed_metric with automated dispatch within 1 minute window
    now = time.time()
    # Feed baseline
    for i, val in enumerate(historical_latencies):
        detector.feed_metric("llm.latency_ms", val, timestamp=now - 600 + i)

    # Feed latency spike within 1 minute of current time
    spike_alert = detector.feed_metric("llm.latency_ms", spike_val, timestamp=now)
    assert spike_alert is not None
    assert len(detector.alerts) >= 1
    assert len(dispatched) >= 1
    assert any("webhook" in dest for dest in spike_alert.dispatched_to)
    assert any("slack" in dest for dest in spike_alert.dispatched_to)
    assert any("email" in dest for dest in spike_alert.dispatched_to)


def test_error_rate_and_traffic_anomaly_detection():
    """Verify anomaly detection across error rate percentages."""
    detector = AnomalyDetector(baseline_window=3600, sigma_threshold=3.0)

    # Normal error rate around 0.5%
    baseline_errors = [0.004, 0.005, 0.006, 0.005, 0.004, 0.005] * 5
    spike_error_rate = 0.15  # 15% error rate spike

    alert = detector.detect("http.error_rate", spike_error_rate, baseline_errors)
    assert alert is not None
    assert alert.metric == "http.error_rate"
    assert alert.z_score > 3.0


def test_signoz_integration():
    """Verify detector can be wired to SigNoz adapter telemetry."""
    signoz = SigNozAdapter()
    detector = AnomalyDetector(signoz_adapter=signoz)

    # Feed metrics to SigNoz and detector simultaneously
    for _ in range(20):
        rec = signoz.record_metric("engine.latency", 50.0)
        detector.feed_metric(rec.name, rec.value)

    # Massive spike
    spike_rec = signoz.record_metric("engine.latency", 500.0)
    alert = detector.feed_metric(spike_rec.name, spike_rec.value)
    assert alert is not None
    assert alert.z_score > 3.0
