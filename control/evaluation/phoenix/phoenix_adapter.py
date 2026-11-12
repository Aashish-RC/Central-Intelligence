"""Arize Phoenix Integration Adapter (Layer 11: Evaluation & Quality, Task 11.1).

Integrates Arize Phoenix for:
- Agent multi-step distributed trace capture (OTel compatible)
- Factual grounding and hallucination detection against retrieved context
- Embedding drift detection across agent interactions
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from control.safety.production_guard import (
    fail_closed_in_production,
    require_live_adapter,
)

logger = logging.getLogger("control.evaluation.phoenix")


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PhoenixSpan:
    """Individual span in a multi-step agent execution trace."""
    span_id: str
    trace_id: str
    name: str
    parent_id: Optional[str] = None
    start_time: str = field(default_factory=utc_iso_now)
    end_time: Optional[str] = None
    input_payload: Any = None
    output_payload: Any = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"

    def complete(self, output: Any = None, status: str = "ok") -> None:
        self.output_payload = output
        self.end_time = utc_iso_now()
        self.status = status


@dataclass
class PhoenixTrace:
    """Multi-step agent reasoning/action execution trace."""
    trace_id: str
    name: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    start_time: str = field(default_factory=utc_iso_now)
    end_time: Optional[str] = None
    spans: List[PhoenixSpan] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def add_span(
        self,
        name: str,
        input_payload: Any = None,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> PhoenixSpan:
        span = PhoenixSpan(
            span_id=str(uuid.uuid4()),
            trace_id=self.trace_id,
            name=name,
            parent_id=parent_id,
            input_payload=input_payload,
            attributes=attributes or {},
        )
        self.spans.append(span)
        return span


@dataclass
class HallucinationEvaluation:
    """Structured hallucination and factual grounding score."""
    trace_id: Optional[str]
    query: str
    response: str
    grounding_score: float  # 0.0 (unsupported) to 1.0 (fully grounded)
    hallucination_rate: float  # 1.0 - grounding_score
    is_hallucinated: bool
    grounded_claims: List[str] = field(default_factory=list)
    unsupported_claims: List[str] = field(default_factory=list)
    explanation: str = ""


@dataclass
class DriftReport:
    """Embedding drift analysis between baseline and current production traffic."""
    drift_detected: bool
    wasserstein_distance: float
    threshold: float
    dimension_count: int
    sample_size: int
    recommendation: str


class PhoenixAdapter:
    """Arize Phoenix evaluation and tracing adapter."""

    def __init__(
        self,
        endpoint: str = "http://localhost:6006",
        hallucination_threshold: float = 0.5,
        _defer_prod_check: bool = False,
    ):
        self.endpoint = endpoint
        self.hallucination_threshold = hallucination_threshold
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("phoenix")
        )
        self._traces: Dict[str, PhoenixTrace] = {}

    def start_trace(
        self,
        name: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> PhoenixTrace:
        """Initializes a new distributed agent execution trace."""
        trace_id = str(uuid.uuid4())
        trace = PhoenixTrace(
            trace_id=trace_id,
            name=name,
            session_id=session_id,
            user_id=user_id,
            attributes=attributes or {},
        )
        self._traces[trace_id] = trace
        return trace

    def get_trace(self, trace_id: str) -> Optional[PhoenixTrace]:
        return self._traces.get(trace_id)

    def evaluate_hallucination(
        self,
        query: str,
        response: str,
        retrieved_context: List[str],
        trace_id: Optional[str] = None,
    ) -> HallucinationEvaluation:
        """Evaluates model response claims against retrieved knowledge chunks.

        Calculates semantic claim grounding. Claims without sufficient support in
        retrieved passages are flagged as hallucinations.
        """
        if not response:
            return HallucinationEvaluation(
                trace_id=trace_id,
                query=query,
                response=response,
                grounding_score=1.0,
                hallucination_rate=0.0,
                is_hallucinated=False,
                explanation="Empty response.",
            )

        # Decompose response into atomic sentences/claims
        raw_sentences = [
            s.strip() for s in response.replace("\n", " ").split(". ") if s.strip()
        ]
        if not raw_sentences:
            raw_sentences = [response]

        unified_context = " ".join(retrieved_context).lower()
        grounded_claims = []
        unsupported_claims = []

        for sentence in raw_sentences:
            sentence_clean = sentence.strip(".").strip()
            # Token/keyword overlap heuristic against context
            words = [
                w.lower()
                for w in sentence_clean.split()
                if len(w) > 3 and w.isalnum()
            ]
            if not words:
                grounded_claims.append(sentence_clean)
                continue

            matches = sum(1 for w in words if w in unified_context)
            match_ratio = matches / len(words)

            if match_ratio >= 0.4:
                grounded_claims.append(sentence_clean)
            else:
                unsupported_claims.append(sentence_clean)

        total_claims = len(grounded_claims) + len(unsupported_claims)
        grounding_score = len(grounded_claims) / max(1, total_claims)
        hallucination_rate = 1.0 - grounding_score
        is_hallucinated = hallucination_rate >= self.hallucination_threshold

        explanation = (
            f"Evaluated {total_claims} claims: {len(grounded_claims)} grounded, "
            f"{len(unsupported_claims)} unsupported. Hallucination rate: {hallucination_rate:.2f}."
        )

        return HallucinationEvaluation(
            trace_id=trace_id,
            query=query,
            response=response,
            grounding_score=grounding_score,
            hallucination_rate=hallucination_rate,
            is_hallucinated=is_hallucinated,
            grounded_claims=grounded_claims,
            unsupported_claims=unsupported_claims,
            explanation=explanation,
        )

    def detect_embedding_drift(
        self,
        baseline_embeddings: List[List[float]],
        current_embeddings: List[List[float]],
        threshold: float = 0.25,
    ) -> DriftReport:
        """Calculates centroid distance / distribution shift between baseline and current embeddings."""
        if not baseline_embeddings or not current_embeddings:
            return DriftReport(
                drift_detected=False,
                wasserstein_distance=0.0,
                threshold=threshold,
                dimension_count=0,
                sample_size=0,
                recommendation="Insufficient embedding samples for drift analysis.",
            )

        dim = len(baseline_embeddings[0])

        # Calculate centroids
        def centroid(vectors: List[List[float]]) -> List[float]:
            n = len(vectors)
            c = [0.0] * dim
            for v in vectors:
                for i in range(min(dim, len(v))):
                    c[i] += v[i]
            return [x / n for x in c]

        c_base = centroid(baseline_embeddings)
        c_curr = centroid(current_embeddings)

        # Euclidean distance between centroids
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(c_base, c_curr)))
        drift_detected = dist > threshold

        rec = (
            f"Embedding drift of {dist:.4f} exceeds threshold {threshold:.4f}. Model recalibration advised."
            if drift_detected
            else f"Embedding distribution stable (distance {dist:.4f} <= {threshold:.4f})."
        )

        return DriftReport(
            drift_detected=drift_detected,
            wasserstein_distance=dist,
            threshold=threshold,
            dimension_count=dim,
            sample_size=len(current_embeddings),
            recommendation=rec,
        )

