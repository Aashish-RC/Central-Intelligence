"""Data models and telemetry definitions for Layer 14 Observability."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class TraceStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


@dataclass
class SpanRecord:
    """Distributed tracing span spanning system layers (L1 through L18)."""
    span_id: str = field(default_factory=lambda: str(uuid4())[:16])
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    parent_span_id: Optional[str] = None
    name: str = "operation"
    layer: str = "L4"
    status: TraceStatus = TraceStatus.OK
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def finish(self, status: TraceStatus = TraceStatus.OK) -> None:
        if self.end_time is None:
            self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000.0
        self.status = status


@dataclass
class MetricRecord:
    """Operational metric measurement (gauge, counter, or histogram value)."""
    name: str
    value: float
    metric_type: str = "gauge"  # 'counter', 'gauge', 'histogram'
    unit: str = "ms"
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class PercentileMetrics:
    """Computed latency distribution percentiles."""
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    sample_count: int
