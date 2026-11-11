"""Periodic In-App NPS Survey Delivery & Aggregation (L7 Feature 7.07)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class NPSSurveyResponse:
    """Single 0-10 Net Promoter Score survey response."""

    user_id: str
    score: int
    comment: str = ""
    cohort: str = "default"
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not (0 <= int(self.score) <= 10):
            raise ValueError(f"NPS score must be between 0 and 10, got {self.score}")
        self.score = int(self.score)

    @property
    def bucket(self) -> str:
        if self.score >= 9:
            return "promoter"
        if self.score >= 7:
            return "passive"
        return "detractor"


@dataclass
class NPSBreakdown:
    total_responses: int
    promoters: int
    passives: int
    detractors: int
    nps_score: float  # -100.0 to +100.0


class NPSSurveyManager:
    """Controls periodic NPS survey prompting cadence and aggregates NPS scores."""

    def __init__(self, cooldown_seconds: float = 30 * 86400.0) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._last_prompted: Dict[str, float] = {}
        self._responses: List[NPSSurveyResponse] = []

    def should_deliver(self, user_id: str, now: float | None = None) -> bool:
        ref = now if now is not None else time.time()
        prev = self._last_prompted.get(user_id)
        return prev is None or (ref - prev) >= self.cooldown_seconds

    def deliver_prompt(self, user_id: str, now: float | None = None) -> Dict[str, object]:
        ref = now if now is not None else time.time()
        if not self.should_deliver(user_id, now=ref):
            return {"delivered": False, "reason": "cooldown_active"}
        self._last_prompted[user_id] = ref
        return {
            "delivered": True,
            "question": "How likely are you to recommend this assistant to a colleague? (0-10)",
            "scale": list(range(11)),
        }

    def record_response(
        self,
        user_id: str,
        score: int,
        comment: str = "",
        cohort: str = "default",
    ) -> NPSSurveyResponse:
        resp = NPSSurveyResponse(user_id=user_id, score=score, comment=comment, cohort=cohort)
        self._responses.append(resp)
        return resp

    def aggregate_nps(self, cohort: str | None = None) -> NPSBreakdown:
        rows = [r for r in self._responses if cohort is None or r.cohort == cohort]
        if not rows:
            return NPSBreakdown(0, 0, 0, 0, 0.0)
        promoters = sum(1 for r in rows if r.bucket == "promoter")
        passives = sum(1 for r in rows if r.bucket == "passive")
        detractors = sum(1 for r in rows if r.bucket == "detractor")
        n = len(rows)
        nps = round(((promoters - detractors) / n) * 100.0, 2)
        return NPSBreakdown(
            total_responses=n,
            promoters=promoters,
            passives=passives,
            detractors=detractors,
            nps_score=nps,
        )

