"""Ordered, Replayable Event Streams with Time-Travel Queries (L15 Feature 15.29)."""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class StreamRecord:
    """Single immutable event stored in a replayable topic log."""

    topic: str
    offset: int
    timestamp: float
    payload: Dict[str, Any]
    key: Optional[str] = None


class ReplayableEventStream:
    """Append-only ordered event log supporting offset and timestamp time-travel replay."""

    def __init__(self) -> None:
        self._logs: Dict[str, List[StreamRecord]] = {}

    def append(
        self,
        topic: str,
        payload: Dict[str, Any],
        timestamp: Optional[float] = None,
        key: Optional[str] = None,
    ) -> StreamRecord:
        log = self._logs.setdefault(topic, [])
        offset = len(log)
        rec = StreamRecord(
            topic=topic,
            offset=offset,
            timestamp=time.time() if timestamp is None else float(timestamp),
            payload=dict(payload),
            key=key,
        )
        log.append(rec)
        return rec

    def replay_from_offset(
        self,
        topic: str,
        start_offset: int = 0,
        end_offset: Optional[int] = None,
    ) -> List[StreamRecord]:
        """Return ordered records from ``start_offset`` (inclusive) to ``end_offset`` (exclusive)."""
        log = self._logs.get(topic, [])
        if start_offset < 0:
            raise ValueError("start_offset must be non-negative")
        return list(log[start_offset:end_offset])

    def replay_from_timestamp(
        self,
        topic: str,
        since_ts: float,
        until_ts: Optional[float] = None,
    ) -> List[StreamRecord]:
        """Time-travel query returning all events with ``timestamp >= since_ts`` (and ``<= until_ts``)."""
        log = self._logs.get(topic, [])
        out: List[StreamRecord] = []
        for rec in log:
            if rec.timestamp < since_ts:
                continue
            if until_ts is not None and rec.timestamp > until_ts:
                continue
            out.append(rec)
        return out

    async def replay_into(
        self,
        topic: str,
        handler: Callable[[StreamRecord], Any],
        since_ts: Optional[float] = None,
        start_offset: int = 0,
    ) -> int:
        records = (
            self.replay_from_timestamp(topic, since_ts)
            if since_ts is not None
            else self.replay_from_offset(topic, start_offset)
        )
        for rec in records:
            res = handler(rec)
            if inspect.isawaitable(res):
                await res
        return len(records)

    def latest_offset(self, topic: str) -> int:
        return len(self._logs.get(topic, []))

