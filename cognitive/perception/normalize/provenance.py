"""
Multi-Modal Provenance and Event Tagging (Layer 1: Perception, Task 1.8).

Tags all perception inputs with origin source, sensory modality, temporal timestamps,
and cryptographic trust levels before dispatching to downstream reasoning layers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4


class TrustLevel(str, Enum):
    """Integrity and authenticity classification of input sources."""
    HIGH = "high"          # Direct authenticated user input, signed tokens
    INTERNAL = "internal"  # Internal system monitors, secure daemons
    MEDIUM = "medium"      # Verified external integrations (LiveKit, Screenpipe)
    LOW = "low"            # Unauthenticated web scrapes, public crawls
    UNTRUSTED = "untrusted"


class InputModality(str, Enum):
    """Sensory modalities handled by the Perception layer."""
    AUDIO = "audio"
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    SCREEN_OCR = "screen_ocr"
    ACCESSIBILITY = "accessibility"


def utc_now() -> float:
    return time.time()


@dataclass
class EventProvenance:
    """Detailed audit metadata establishing the origin of an input event."""
    source: str
    trust: str
    timestamp: float = field(default_factory=utc_now)
    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedEvent:
    """Unified temporal event aggregating multi-modal inputs."""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    content: Any = None
    source: str = "user"           # "livekit", "handy", "crawl4ai", "screenpipe", "user"
    trust: str = "high"
    modality: str = "text"         # "audio", "text", "image", "video", "document"
    timestamp: float = field(default_factory=utc_now)
    provenance: Optional[EventProvenance] = None

    def __post_init__(self) -> None:
        if self.provenance is None:
            self.provenance = EventProvenance(
                source=self.source,
                trust=self.trust,
                timestamp=self.timestamp,
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "content": str(self.content) if isinstance(self.content, (bytes, memoryview)) else self.content,
            "source": self.source,
            "trust": self.trust,
            "modality": self.modality,
            "timestamp": self.timestamp,
            "provenance": {
                "source": self.provenance.source if self.provenance else self.source,
                "trust": self.provenance.trust if self.provenance else self.trust,
                "captured_at": self.provenance.captured_at if self.provenance else "",
                "metadata": self.provenance.metadata if self.provenance else {},
            },
        }

