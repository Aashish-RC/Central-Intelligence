"""Routing Strategy A/B Testing (Layer 11: Evaluation & Quality, Feature 11.20)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .significance import SignificanceResult, calculate_significance


class RoutingABTestRunner:
    """A/B Testing harness comparing routing policies (e.g. Cost vs Latency)."""

    def __init__(self, experiment_id: str, policy_a: str, policy_b: str):
        self.experiment_id = experiment_id
        self.policy_a = policy_a
        self.policy_b = policy_b
        self.latencies_a: List[float] = []
        self.latencies_b: List[float] = []

    def select_policy(self, session_id: str) -> str:
        h = int(hashlib.md5(f"{self.experiment_id}:{session_id}".encode()).hexdigest(), 16)
        return self.policy_a if (h % 2 == 0) else self.policy_b

    def record_latency(self, policy: str, latency_ms: float) -> None:
        if policy == self.policy_a:
            self.latencies_a.append(latency_ms)
        elif policy == self.policy_b:
            self.latencies_b.append(latency_ms)

    def analyze(self) -> SignificanceResult:
        return calculate_significance(self.latencies_a, self.latencies_b)

