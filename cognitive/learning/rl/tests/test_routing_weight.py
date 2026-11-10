"""Unit tests for Routing Weight RL Adjuster (Feature 7.12)."""

import pytest
from cognitive.learning.rl.routing_weight_adjuster import (
    RoutingWeightAdjuster,
    FeedbackEvent,
)


def test_10_thumbs_up_for_claude_on_coding_gets_higher_weight():
    adjuster = RoutingWeightAdjuster(lr=0.05, default_weight=0.5)

    candidates = ["claude-3-5-sonnet", "gpt-4o", "gemini-2.5-pro"]

    initial_weights = adjuster.get_weights("coding")
    assert initial_weights.get("claude-3-5-sonnet", 0.5) == 0.5

    # Submit 10 consecutive thumbs-up for Claude on coding
    for _ in range(10):
        adjuster.record_feedback(task_type="coding", model="claude-3-5-sonnet", rating="thumbs_up")

    updated_weights = adjuster.get_weights("coding")
    claude_weight = updated_weights["claude-3-5-sonnet"]

    # 0.5 + 10 * 0.05 = 1.0
    assert claude_weight >= 0.95
    assert claude_weight > updated_weights.get("gpt-4o", 0.5)

    # Best model selection should now unambiguously pick Claude
    best = adjuster.select_best_model("coding", candidates)
    assert best == "claude-3-5-sonnet"


def test_negative_feedback_lowers_model_weight():
    adjuster = RoutingWeightAdjuster(lr=0.1, default_weight=0.5)

    # 3 negative feedback signals
    for _ in range(3):
        adjuster.record_feedback(task_type="translation", model="legacy-model", rating="thumbs_down")

    weights = adjuster.get_weights("translation")
    assert weights["legacy-model"] <= 0.25


def test_softmax_probabilities_reflect_learning():
    adjuster = RoutingWeightAdjuster(lr=0.1, default_weight=0.5)

    # Boost gpt-4o on reasoning
    for _ in range(5):
        adjuster.update("reasoning", "gpt-4o", reward=1.0)

    probs = adjuster.get_normalized_probabilities("reasoning", ["gpt-4o", "other-model"])
    assert probs["gpt-4o"] > probs["other-model"]
