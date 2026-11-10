"""Tier 1 Telemetry Sink (Layer 10: Safety, Feature 10.30; Layer 14: Observability, Feature 14.19).

Tier 1: Non-PII technical metadata (token metrics, latency, model ID, cost estimation,
pseudonymized / SHA-256 hashed user ID). Retained 90–365 days.
Wires to Layer 14 SigNoz / OpenTelemetry collectors.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def hash_user_id(user_id: str, salt: str = "central_intelligence_telemetry") -> str:
    """Generates a irreversible pseudonymized SHA-256 hash for telemetry correlation."""
    if not user_id:
        return "anon"
    return hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:16]


@dataclass
class TelemetryMetricRecord:
    metric_id: str
    user_hash: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    cost_usd: float
    timestamp: float = field(default_factory=time.time)
    retained_days: int = 90
    metadata: Dict[str, Any] = field(default_factory=dict)


class Tier1TelemetrySink:
    """In-memory & exporter sink for Tier 1 non-PII operational telemetry."""

    def __init__(self, default_ttl_days: int = 90):
        self.default_ttl_days = default_ttl_days
        self._records: List[TelemetryMetricRecord] = []

    def store(
        self,
        payload: Dict[str, Any],
        user_id: str,
        retained_days: Optional[int] = None,
    ) -> TelemetryMetricRecord:
        """Sanitizes and stores technical metadata, strictly anonymizing the user identifier."""
        u_hash = hash_user_id(user_id)
        ttl = retained_days if retained_days is not None else self.default_ttl_days

        rec = TelemetryMetricRecord(
            metric_id=payload.get("metric_id", f"met_{int(time.time()*1000)}"),
            user_hash=u_hash,
            model=payload.get("model", "unknown"),
            prompt_tokens=payload.get("prompt_tokens", 0),
            completion_tokens=payload.get("completion_tokens", 0),
            total_tokens=payload.get("total_tokens", 0),
            latency_ms=payload.get("latency_ms", 0.0),
            cost_usd=payload.get("cost_usd", 0.0),
            timestamp=time.time(),
            retained_days=ttl,
            metadata={k: v for k, v in payload.items() if k not in {
                "metric_id", "model", "prompt_tokens", "completion_tokens",
                "total_tokens", "latency_ms", "cost_usd", "user_id"
            }},
        )
        self._records.append(rec)
        return rec

    def get_records(self, user_id: Optional[str] = None) -> List[TelemetryMetricRecord]:
        if user_id:
            u_hash = hash_user_id(user_id)
            return [r for r in self._records if r.user_hash == u_hash]
        return list(self._records)

    def purge(self, user_id: str) -> int:
        """Purges all telemetry tied to the pseudonymized user hash for GDPR/Right-to-Erasure."""
        u_hash = hash_user_id(user_id)
        initial_len = len(self._records)
        self._records = [r for r in self._records if r.user_hash != u_hash]
        return initial_len - len(self._records)

    def delete_expired(self, current_time: Optional[float] = None) -> int:
        """Purges telemetry records older than their retained_days."""
        now = current_time if current_time is not None else time.time()
        initial_len = len(self._records)
        self._records = [
            r for r in self._records
            if not (r.timestamp and (now - r.timestamp) > (r.retained_days * 86400))
        ]
        return initial_len - len(self._records)


