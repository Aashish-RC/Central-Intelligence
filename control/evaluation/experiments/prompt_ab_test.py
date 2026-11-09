"""Prompt & Instruction A/B Testing (Layer 11: Evaluation & Quality, Feature 11.19)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .significance import SignificanceResult, calculate_significance


@dataclass
class PromptVariantResult:
    variant_id: str
    scores: List[float] = field(default_factory=list)


class PromptABTestRunner:
    """A/B Testing harness comparing prompt template variants."""

    def __init__(self, experiment_id: str, variant_a_id: str, variant_b_id: str):
        self.experiment_id = experiment_id
        self.variant_a = PromptVariantResult(variant_id=variant_a_id)
        self.variant_b = PromptVariantResult(variant_id=variant_b_id)

    def route_variant(self, user_id: str) -> str:
        h = int(hashlib.sha256(f"{self.experiment_id}:{user_id}".encode()).hexdigest(), 16)
        return self.variant_a.variant_id if (h % 2 == 0) else self.variant_b.variant_id

    def record_score(self, variant_id: str, score: float) -> None:
        if variant_id == self.variant_a.variant_id:
            self.variant_a.scores.append(score)
        elif variant_id == self.variant_b.variant_id:
            self.variant_b.scores.append(score)

    def analyze(self) -> SignificanceResult:
        return calculate_significance(self.variant_a.scores, self.variant_b.scores)
