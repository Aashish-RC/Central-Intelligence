"""
Unified Input Normalizer and Synchronized Event Queue (Layer 1: Perception, Task 1.8).

Streams WebRTC audio chunks, screen OCR diffs, documents, and typed text into a single
temporally synchronized event queue with provenance tagging.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from cognitive.perception.normalize.provenance import (
    EventProvenance,
    InputModality,
    NormalizedEvent,
    TrustLevel,
    utc_now,
)

logger = logging.getLogger("cognitive.perception.normalize.queue")

DEFAULT_SOURCE_TRUST: Dict[str, str] = {
    "user": TrustLevel.HIGH.value,
    "livekit": TrustLevel.MEDIUM.value,
    "handy": TrustLevel.HIGH.value,
    "screenpipe": TrustLevel.MEDIUM.value,
    "crawl4ai": TrustLevel.LOW.value,
    "unstructured": TrustLevel.MEDIUM.value,
    "paddleocr": TrustLevel.MEDIUM.value,
    "vlm": TrustLevel.INTERNAL.value,
}


class InputNormalizer:
    """
    Unified streaming normalizer for all multi-modal perception sources (Task 1.8).
    Synchronizes temporal inputs and tags provenance before handoff to L4/L9.
    """

    def __init__(self, sources: Optional[Dict[str, str]] = None) -> None:
        self.event_queue: asyncio.Queue[NormalizedEvent] = asyncio.Queue()
        self.sources: Dict[str, str] = dict(DEFAULT_SOURCE_TRUST)
        if sources:
            self.sources.update(sources)
        self._history: List[NormalizedEvent] = []

    def set_source_trust(self, source_name: str, trust_level: str | TrustLevel) -> None:
        """Configures or overrides the trust level for a specific input source."""
        lvl = trust_level.value if isinstance(trust_level, TrustLevel) else trust_level
        self.sources[source_name] = lvl

    async def ingest(
        self,
        raw_input: Any,
        source: str,
        modality: str | InputModality,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NormalizedEvent:
        """
        Acceptance: Audio from LiveKit + text from user + OCR from screenpipe are all
        in the same event queue with correct timestamps and provenance.
        """
        mod = modality.value if isinstance(modality, InputModality) else str(modality)
        ts = timestamp if timestamp is not None else utc_now()
        trust = self.sources.get(source, TrustLevel.LOW.value)

        prov = EventProvenance(
            source=source,
            trust=trust,
            timestamp=ts,
            metadata=metadata or {},
        )

        event = NormalizedEvent(
            event_id=str(uuid4()),
            content=raw_input,
            source=source,
            trust=trust,
            modality=mod,
            timestamp=ts,
            provenance=prov,
        )

        await self.event_queue.put(event)
        self._history.append(event)
        return event

    def ingest_sync(
        self,
        raw_input: Any,
        source: str,
        modality: str | InputModality,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NormalizedEvent:
        """Synchronous wrapper for ingest."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Direct put_nowait if loop is active in thread
                mod = modality.value if isinstance(modality, InputModality) else str(modality)
                ts = timestamp if timestamp is not None else utc_now()
                trust = self.sources.get(source, TrustLevel.LOW.value)
                prov = EventProvenance(source=source, trust=trust, timestamp=ts, metadata=metadata or {})
                event = NormalizedEvent(
                    event_id=str(uuid4()),
                    content=raw_input,
                    source=source,
                    trust=trust,
                    modality=mod,
                    timestamp=ts,
                    provenance=prov,
                )
                self.event_queue.put_nowait(event)
                self._history.append(event)
                return event
            return loop.run_until_complete(self.ingest(raw_input, source, modality, timestamp, metadata))
        except RuntimeError:
            return asyncio.run(self.ingest(raw_input, source, modality, timestamp, metadata))

    async def consume(self) -> NormalizedEvent:
        """Consumes the next temporal event from the synchronized queue."""
        return await self.event_queue.get()

    def get_history(self) -> List[NormalizedEvent]:
        """Returns all ingested events in chronological order."""
        return list(self._history)

    def size(self) -> int:
        """Returns the number of queued events waiting to be processed."""
        return self.event_queue.qsize()


# Global default normalizer instance
default_input_normalizer = InputNormalizer()
