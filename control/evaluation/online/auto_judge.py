"""Automated Judge Scoring on Live Traffic (Layer 11: Evaluation & Quality, Feature 11.06)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class JudgeScore:
    """Individual rubric evaluation result."""
    dimension: str  # e.g., 'relevance', 'groundedness', 'coherence', 'safety'
    score: float  # 0.0 to 1.0
    passed: bool
    reason: str = ""


@dataclass
class AutoJudgeEvaluation:
    """Aggregated evaluation across dimensions by automated judge."""
    trace_id: str
    overall_score: float
    passed: bool
    scores: List[JudgeScore]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AutoJudge:
    """Evaluates live conversation traffic along multiple quality dimensions."""

    def __init__(self, pass_threshold: float = 0.70):
        self.pass_threshold = pass_threshold

    def evaluate(
        self,
        trace_id: str,
        query: str,
        response: str,
        context: Optional[str] = None,
    ) -> AutoJudgeEvaluation:
        scores: List[JudgeScore] = []

        # 1. Relevance
        q_words = set(re.findall(r"\w+", query.lower()))
        r_words = set(re.findall(r"\w+", response.lower()))
        overlap = len(q_words & r_words)
        relevance_score = min(1.0, (overlap / max(1, len(q_words))) * 1.5)
        scores.append(
            JudgeScore(
                dimension="relevance",
                score=round(relevance_score, 2),
                passed=relevance_score >= self.pass_threshold,
                reason="Adequate keyword alignment with query" if relevance_score >= 0.5 else "Low query overlap",
            )
        )

        # 2. Coherence (length and structure)
        words = response.split()
        coherence = 1.0 if len(words) >= 3 else 0.3
        scores.append(
            JudgeScore(
                dimension="coherence",
                score=coherence,
                passed=coherence >= self.pass_threshold,
                reason="Sufficient depth and sentence structure",
            )
        )

        # 3. Groundedness (if context provided)
        if context:
            c_words = set(re.findall(r"\w+", context.lower()))
            c_overlap = len(r_words & c_words)
            groundedness = min(1.0, c_overlap / max(1, len(r_words)))
            scores.append(
                JudgeScore(
                    dimension="groundedness",
                    score=round(groundedness, 2),
                    passed=groundedness >= self.pass_threshold,
                    reason="Response supported by context",
                )
            )

        overall = sum(s.score for s in scores) / len(scores)
        passed = overall >= self.pass_threshold

        return AutoJudgeEvaluation(
            trace_id=trace_id,
            overall_score=round(overall, 2),
            passed=passed,
            scores=scores,
        )
