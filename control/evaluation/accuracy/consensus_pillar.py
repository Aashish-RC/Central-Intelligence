"""Consensus Pillar: S_consensus (Layer 11: Evaluation & Quality, Feature 11.14).

Computes cross-model agreement score across multiple candidate models from MoA fusion.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CandidatePrediction:
    """Individual model candidate response."""
    model_name: str
    content: str
    confidence: float = 1.0


class ConsensusPillar:
    """Calculates multi-model consensus agreement score S_consensus."""

    def __init__(self, default_neutral_score: float = 0.50):
        self.default_neutral_score = default_neutral_score
        self._task_candidates: Dict[str, List[CandidatePrediction]] = {}

    def register_candidates(self, task_id: str, candidates: List[CandidatePrediction]) -> None:
        self._task_candidates[task_id] = list(candidates)

    def has_consensus_data(self, task_id: str) -> bool:
        return task_id in self._task_candidates and len(self._task_candidates[task_id]) >= 2

    def agreement_score(self, task_id: str) -> float:
        """Computes pairwise semantic sequence agreement across candidate predictions."""
        if not self.has_consensus_data(task_id):
            return self.default_neutral_score

        candidates = self._task_candidates[task_id]
        if len(candidates) < 2:
            return self.default_neutral_score

        ratios: List[float] = []
        texts = [c.content.strip().lower() for c in candidates]

        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                sm = difflib.SequenceMatcher(None, texts[i], texts[j])
                ratios.append(sm.ratio())

        if not ratios:
            return self.default_neutral_score

        return round(sum(ratios) / len(ratios), 4)

    def calculate_direct_consensus(self, candidate_texts: List[str]) -> float:
        """Calculates direct consensus score from a list of candidate strings."""
        if len(candidate_texts) < 2:
            return self.default_neutral_score

        ratios: List[float] = []
        texts = [t.strip().lower() for t in candidate_texts]

        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                sm = difflib.SequenceMatcher(None, texts[i], texts[j])
                ratios.append(sm.ratio())

        return round(sum(ratios) / len(ratios), 4)

