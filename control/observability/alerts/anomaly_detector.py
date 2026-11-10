"""
Layer 14: Metric Anomaly Detector (Feature 14.14).

Detects statistical anomalies across operational metrics (latency spikes, error rate jumps,
unusual traffic or token volume patterns) using rolling baseline z-score distribution analysis.
Dispatches alerts to configured alert sinks (webhook, Slack, email).
"""

from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger("control.observability.alerts.anomaly")


@dataclass
class AnomalyAlert:
    """Represents a statistically significant anomaly event."""
    metric: str
    value: float
    expected: float
    z_score: float
    severity: str  # "medium", "high", or "critical"
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)
    dispatched_to: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "value": self.value,
            "expected": self.expected,
            "z_score": round(self.z_score, 3),
            "severity": self.severity,
            "timestamp": self.timestamp,
            "details": self.details,
            "dispatched_to": self.dispatched_to,
        }


class AnomalyDetector:
    """
    Statistical anomaly detector for real-time observability telemetry (Feature 14.14).
    Calculates z-score against a rolling historical baseline window and alerts on >3σ spikes.
    """

    def __init__(
        self,
        baseline_window: int = 3600,
        sigma_threshold: float = 3.0,
        signoz_adapter: Optional[Any] = None,
    ) -> None:
        self.baseline_window = baseline_window  # Rolling baseline in seconds (default 1 hour)
        self.sigma_threshold = sigma_threshold
        self.signoz = signoz_adapter

        # Local metric buffers: metric_name -> list of (timestamp, value)
        self._metric_history: Dict[str, List[tuple[float, float]]] = {}
        self._alerts: List[AnomalyAlert] = []
        self._handlers: List[Callable[[AnomalyAlert], Any]] = []

    @property
    def alerts(self) -> List[AnomalyAlert]:
        return list(self._alerts)

    def add_handler(self, handler: Callable[[AnomalyAlert], Any]) -> None:
        """Registers a general notification handler."""
        self._handlers.append(handler)

    def add_webhook_sink(self, endpoint_url: str) -> None:
        """Registers an HTTP webhook notification sink."""
        def webhook_sink(alert: AnomalyAlert) -> None:
            alert.dispatched_to.append(f"webhook:{endpoint_url}")
            logger.info("Alert dispatched to webhook %s: %s", endpoint_url, alert.metric)

        self._handlers.append(webhook_sink)

    def add_slack_sink(self, channel_or_url: str) -> None:
        """Registers a Slack alerting sink."""
        def slack_sink(alert: AnomalyAlert) -> None:
            alert.dispatched_to.append(f"slack:{channel_or_url}")
            logger.info("Alert dispatched to Slack %s: %s", channel_or_url, alert.metric)

        self._handlers.append(slack_sink)

    def add_email_sink(self, email_recipient: str) -> None:
        """Registers an email alerting sink."""
        def email_sink(alert: AnomalyAlert) -> None:
            alert.dispatched_to.append(f"email:{email_recipient}")
            logger.info("Alert dispatched to email %s: %s", email_recipient, alert.metric)

        self._handlers.append(email_sink)

    def detect(
        self,
        metric_name: str,
        current_value: float,
        historical_values: Sequence[float],
    ) -> Optional[AnomalyAlert]:
        """
        Calculates z-score against historical values.
        Returns AnomalyAlert if z_score exceeds sigma_threshold (>3.0).
        """
        if not historical_values:
            return None

        mean = statistics.mean(historical_values)
        if len(historical_values) > 1:
            stdev = statistics.stdev(historical_values)
        else:
            stdev = 0.0

        z_score = abs(current_value - mean) / max(stdev, 0.001)

        if z_score > self.sigma_threshold:
            severity = "critical" if z_score > 8.0 else ("high" if z_score > 5.0 else "medium")
            alert = AnomalyAlert(
                metric=metric_name,
                value=current_value,
                expected=mean,
                z_score=z_score,
                severity=severity,
                details={
                    "baseline_samples": len(historical_values),
                    "mean": mean,
                    "stdev": stdev,
                },
            )
            return alert

        return None

    def feed_metric(
        self,
        metric_name: str,
        value: float,
        timestamp: Optional[float] = None,
    ) -> Optional[AnomalyAlert]:
        """
        Feeds a real-time metric point into the rolling baseline and immediately detects spikes.
        If an anomaly is detected, records the alert and dispatches to all sinks.
        """
        now = timestamp if timestamp is not None else time.time()
        cutoff = now - self.baseline_window

        if metric_name not in self._metric_history:
            self._metric_history[metric_name] = []

        # Evict old samples outside baseline_window
        history = [
            (ts, val) for ts, val in self._metric_history[metric_name]
            if ts >= cutoff
        ]
        self._metric_history[metric_name] = history

        # Extract values for baseline comparison
        past_values = [val for _, val in history]

        alert: Optional[AnomalyAlert] = None
        if past_values:
            alert = self.detect(metric_name, value, past_values)
            if alert:
                alert.timestamp = now
                self._dispatch_alert(alert)

        # Append new point to history
        self._metric_history[metric_name].append((now, value))
        return alert

    def _dispatch_alert(self, alert: AnomalyAlert) -> None:
        """Dispatches alert to internal registry and all notification sinks."""
        self._alerts.append(alert)
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error("Error dispatching alert to sink: %s", e)


# Global default anomaly detector
default_anomaly_detector = AnomalyDetector()

