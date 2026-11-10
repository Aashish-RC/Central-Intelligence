"""Feature Flags and Experimentation subsystem (L17 Release)."""

from .growthbook_adapter import (
    GrowthBookAdapter,
    FeatureFlag,
    EvaluationResult,
)

__all__ = [
    "GrowthBookAdapter",
    "FeatureFlag",
    "EvaluationResult",
]

