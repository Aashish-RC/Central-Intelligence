"""Blind Side-by-Side Preference Evaluation (Layer 11: Evaluation & Quality)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SideBySideVerdict(str, Enum):
    MODEL_A_WINS = "model_a_wins"
    MODEL_B_WINS = "model_b_wins"
    TIE = "tie"


@dataclass
class SideBySideComparison:
    prompt: str
    model_a_output: str
    model_b_output: str
    verdict: SideBySideVerdict
    notes: Optional[str] = None


class SideBySideEvaluator:
    """Manages blind pairwise comparisons between model outputs."""

    def __init__(self, model_a_name: str, model_b_name: str):
        self.model_a_name = model_a_name
        self.model_b_name = model_b_name
        self.comparisons: List[SideBySideComparison] = []

    def record_judgment(
        self,
        prompt: str,
        output_a: str,
        output_b: str,
        verdict: SideBySideVerdict,
        notes: Optional[str] = None,
    ) -> None:
        self.comparisons.append(
            SideBySideComparison(
                prompt=prompt,
                model_a_output=output_a,
                model_b_output=output_b,
                verdict=verdict,
                notes=notes,
            )
        )

    def get_win_rates(self) -> Dict[str, float]:
        if not self.comparisons:
            return {self.model_a_name: 0.0, self.model_b_name: 0.0, "tie": 0.0}

        total = len(self.comparisons)
        wins_a = sum(1 for c in self.comparisons if c.verdict == SideBySideVerdict.MODEL_A_WINS)
        wins_b = sum(1 for c in self.comparisons if c.verdict == SideBySideVerdict.MODEL_B_WINS)
        ties = sum(1 for c in self.comparisons if c.verdict == SideBySideVerdict.TIE)

        return {
            self.model_a_name: round(wins_a / total, 4),
            self.model_b_name: round(wins_b / total, 4),
            "tie": round(ties / total, 4),
        }

