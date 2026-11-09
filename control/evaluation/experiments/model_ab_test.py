"""Model A/B Testing Harness (Layer 11: Evaluation & Quality, Feature 11.18)."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .significance import SignificanceResult, calculate_significance


@dataclass
class ModelObservation:
    """Observation recorded for a model execution."""
    sample_id: str
    model_name: str
    latency_ms: float
    quality_score: float
    cost_tokens: int = 0


@dataclass
class ModelABExperimentReport:
    """Report summarizing model A/B experiment outcome."""
    experiment_id: str
    model_a: str
    model_b: str
    observations_a: int
    observations_b: int
    significance: SignificanceResult
    latency_mean_a: float
    latency_mean_b: float
    winner: Optional[str] = None


class ModelABTestHarness:
    """Manages online and offline A/B comparisons between two candidate models."""

    def __init__(self, experiment_id: str, model_a: str, model_b: str, split_ratio: float = 0.5):
        self.experiment_id = experiment_id
        self.model_a = model_a
        self.model_b = model_b
        self.split_ratio = split_ratio
        self._obs_a: List[ModelObservation] = []
        self._obs_b: List[ModelObservation] = []

    def assign_model(self, session_or_user_id: str) -> str:
        """Deterministic hashing to route traffic stably."""
        h = int(hashlib.md5(f"{self.experiment_id}:{session_or_user_id}".encode()).hexdigest(), 16)
        return self.model_a if (h % 1000) / 1000.0 < self.split_ratio else self.model_b

    def record_run(
        self,
        sample_id: str,
        model_name: str,
        quality_score: float,
        latency_ms: float,
        cost_tokens: int = 0,
    ) -> None:
        obs = ModelObservation(
            sample_id=sample_id,
            model_name=model_name,
            latency_ms=latency_ms,
            quality_score=quality_score,
            cost_tokens=cost_tokens,
        )
        if model_name == self.model_a:
            self._obs_a.append(obs)
        else:
            self._obs_b.append(obs)

    def evaluate_experiment(self) -> ModelABExperimentReport:
        scores_a = [o.quality_score for o in self._obs_a]
        scores_b = [o.quality_score for o in self._obs_b]
        sig = calculate_significance(scores_a, scores_b)

        lat_a = sum(o.latency_ms for o in self._obs_a) / max(1, len(self._obs_a))
        lat_b = sum(o.latency_ms for o in self._obs_b) / max(1, len(self._obs_b))

        winner = None
        if sig.is_significant:
            winner = self.model_b if sig.difference > 0 else self.model_a

        return ModelABExperimentReport(
            experiment_id=self.experiment_id,
            model_a=self.model_a,
            model_b=self.model_b,
            observations_a=len(self._obs_a),
            observations_b=len(self._obs_b),
            significance=sig,
            latency_mean_a=round(lat_a, 2),
            latency_mean_b=round(lat_b, 2),
            winner=winner,
        )
