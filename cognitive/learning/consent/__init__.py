"""Consent management and training-data lineage tracking (Features 7.21, 7.22)."""

from cognitive.learning.consent.consent_manager import (
    TrainingConsentManager,
)
from cognitive.learning.consent.lineage_tracker import (
    TrainingLineageTracker,
    TrainingDataProvenance,
)

__all__ = [
    "TrainingConsentManager",
    "TrainingLineageTracker",
    "TrainingDataProvenance",
]
