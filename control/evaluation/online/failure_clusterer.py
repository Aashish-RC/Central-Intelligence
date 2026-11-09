"""Failure Clustering and Analysis (Layer 11: Evaluation & Quality, Feature 11.09)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FailureIncident:
    """Recorded failure event."""
    incident_id: str
    category: str
    error_message: str
    trace_id: Optional[str] = None
    stack_trace: Optional[str] = None


@dataclass
class FailureCluster:
    """Cluster of related failure incidents."""
    category: str
    count: int
    percentage: float
    sample_errors: List[str] = field(default_factory=list)


class FailureClusterer:
    """Categorizes and clusters runtime failures into root-cause taxonomy."""

    def __init__(self):
        self._incidents: List[FailureIncident] = []

    def record_failure(
        self,
        incident_id: str,
        error_message: str,
        trace_id: Optional[str] = None,
        stack_trace: Optional[str] = None,
    ) -> FailureIncident:
        category = self._classify(error_message)
        inc = FailureIncident(
            incident_id=incident_id,
            category=category,
            error_message=error_message,
            trace_id=trace_id,
            stack_trace=stack_trace,
        )
        self._incidents.append(inc)
        return inc

    def get_clusters(self) -> List[FailureCluster]:
        if not self._incidents:
            return []

        counts: Dict[str, List[str]] = {}
        for inc in self._incidents:
            counts.setdefault(inc.category, []).append(inc.error_message)

        total = len(self._incidents)
        clusters = []
        for cat, errs in counts.items():
            clusters.append(
                FailureCluster(
                    category=cat,
                    count=len(errs),
                    percentage=round(len(errs) / total * 100.0, 1),
                    sample_errors=errs[:3],
                )
            )
        clusters.sort(key=lambda c: c.count, reverse=True)
        return clusters

    def _classify(self, error: str) -> str:
        e = error.lower()
        if "timeout" in e or "deadline" in e:
            return "timeout_exhaustion"
        if "hallucination" in e or "ungrounded" in e:
            return "hallucination_detected"
        if "refus" in e or "safety" in e or "guardrail" in e:
            return "safety_guardrail_trip"
        if "json" in e or "syntax" in e or "parse" in e:
            return "schema_parsing_error"
        if "rate limit" in e or "429" in e:
            return "upstream_rate_limited"
        if "permission" in e or "auth" in e or "denied" in e:
            return "access_control_denied"
        return "unclassified_error"
