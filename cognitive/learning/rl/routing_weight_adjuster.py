"""Routing Weight RL Adjuster (Feature 7.12)

Reinforcement Learning loop shifting model routing weights based on user feedback,
evaluator ratings, and downstream task success.
Wires with L8 orchestration policies and L2 Memory feedback storage.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FeedbackEvent:
    """Feedback signal associated with a model routing execution."""
    task_type: str
    model: str
    reward: float  # +1.0 for positive, -1.0 for negative, or scaled [0, 1]
    metadata: Dict[str, Any] = field(default_factory=dict)


class RoutingWeightAdjuster:
    """Adjusts routing preference weights across candidate models using RL feedback."""

    def __init__(
        self,
        lr: float = 0.05,
        default_weight: float = 0.5,
        min_weight: float = 0.01,
        max_weight: float = 2.0,
    ) -> None:
        self.lr = lr
        self.default_weight = default_weight
        self.min_weight = min_weight
        self.max_weight = max_weight
        # task_type -> {model_id: weight}
        self.weights: Dict[str, Dict[str, float]] = {}
        self.history: List[FeedbackEvent] = []

    def update(self, task_type: str, model: str, reward: float) -> float:
        """Update the routing weight for a model on a given task type."""
        if task_type not in self.weights:
            self.weights[task_type] = {}

        current = self.weights[task_type].get(model, self.default_weight)
        new_weight = current + (self.lr * reward)
        # Clamp to bounds
        new_weight = max(self.min_weight, min(self.max_weight, new_weight))
        self.weights[task_type][model] = round(new_weight, 5)

        self.history.append(FeedbackEvent(task_type=task_type, model=model, reward=reward))
        return new_weight

    def record_feedback(self, task_type: str, model: str, rating: str | int | float) -> float:
        """Convert conversational or UI feedback signals to numerical reward and update."""
        if isinstance(rating, str):
            rating_lower = rating.lower().strip()
            if rating_lower in ["thumbs_up", "up", "positive", "success", "good", "+1"]:
                reward = 1.0
            elif rating_lower in ["thumbs_down", "down", "negative", "failure", "bad", "-1"]:
                reward = -1.0
            else:
                reward = 0.0
        else:
            reward = float(rating)

        return self.update(task_type, model, reward)

    def get_weights(self, task_type: str) -> Dict[str, float]:
        """Return the current routing weight table for a specific task category."""
        return dict(self.weights.get(task_type, {}))

    def select_best_model(self, task_type: str, candidate_models: List[str]) -> str:
        """Select the highest-weighted candidate model for a given task type."""
        if not candidate_models:
            raise ValueError("No candidate models provided for selection.")

        task_weights = self.weights.get(task_type, {})
        # Pick candidate with highest weight, falling back to default_weight
        best_model = max(
            candidate_models,
            key=lambda m: task_weights.get(m, self.default_weight)
        )
        return best_model

    def get_normalized_probabilities(self, task_type: str, candidate_models: List[str]) -> Dict[str, float]:
        """Softmax normalized routing probabilities across candidates."""
        task_weights = self.weights.get(task_type, {})
        raw_weights = [task_weights.get(m, self.default_weight) for m in candidate_models]
        exp_weights = [math.exp(w) for w in raw_weights]
        sum_exp = sum(exp_weights)

        return {
            m: round(exp_w / sum_exp, 4)
            for m, exp_w in zip(candidate_models, exp_weights)
        }
