"""Unified Input Normalization & Event Queue (Layer 1: Perception, Task 1.8)."""

from cognitive.perception.normalize.event_queue import (
    DEFAULT_SOURCE_TRUST,
    InputNormalizer,
    default_input_normalizer,
)
from cognitive.perception.normalize.provenance import (
    EventProvenance,
    InputModality,
    NormalizedEvent,
    TrustLevel,
    utc_now,
)

__all__ = [
    "DEFAULT_SOURCE_TRUST",
    "EventProvenance",
    "InputModality",
    "InputNormalizer",
    "NormalizedEvent",
    "TrustLevel",
    "default_input_normalizer",
    "utc_now",
]

