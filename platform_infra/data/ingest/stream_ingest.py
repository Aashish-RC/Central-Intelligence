"""Real-Time Streaming Data Ingestion Pipeline (L15 Feature 15.32)."""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterable, Callable, Dict, Iterable, List, Optional

TransformFn = Callable[[Dict[str, Any]], Any]
SinkFn = Callable[[List[Dict[str, Any]]], Any]


@dataclass
class StreamIngestStats:
    """Throughput and error telemetry for a streaming ingestion run."""

    received: int = 0
    stored: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def events_per_second(self) -> float:
        if self.elapsed_seconds <= 0:
            return float(self.stored)
        return self.stored / self.elapsed_seconds


class StreamingIngestPipeline:
    """High-throughput ``stream -> transform -> store`` ingestion pipeline."""

    def __init__(
        self,
        transform: Optional[TransformFn] = None,
        sink: Optional[SinkFn] = None,
        batch_size: int = 250,
    ) -> None:
        self.transform = transform or (lambda item: item)
        self._default_store: List[Dict[str, Any]] = []
        self.sink = sink or self._memory_sink
        self.batch_size = max(1, batch_size)

    def _memory_sink(self, records: List[Dict[str, Any]]) -> None:
        self._default_store.extend(records)

    @property
    def stored_records(self) -> List[Dict[str, Any]]:
        return list(self._default_store)

    async def ingest_iterable(self, events: Iterable[Dict[str, Any]]) -> StreamIngestStats:
        """Ingest a synchronous iterable of events through transform and batched sink."""
        start = time.perf_counter()
        stats = StreamIngestStats()
        batch: List[Dict[str, Any]] = []
        for raw in events:
            stats.received += 1
            try:
                transformed = self.transform(raw)
                if inspect.isawaitable(transformed):
                    transformed = await transformed
                if transformed is not None:
                    batch.append(transformed)
                if len(batch) >= self.batch_size:
                    await self._flush(batch, stats)
                    batch = []
            except Exception as exc:  # pragma: no cover - verified by error-handling test
                stats.failed += 1
                stats.errors.append(str(exc))
        if batch:
            await self._flush(batch, stats)
        stats.elapsed_seconds = max(1e-6, time.perf_counter() - start)
        return stats

    async def ingest_async_stream(
        self, events: AsyncIterable[Dict[str, Any]]
    ) -> StreamIngestStats:
        """Ingest an async stream of events through transform and batched sink."""
        start = time.perf_counter()
        stats = StreamIngestStats()
        batch: List[Dict[str, Any]] = []
        async for raw in events:
            stats.received += 1
            try:
                transformed = self.transform(raw)
                if inspect.isawaitable(transformed):
                    transformed = await transformed
                if transformed is not None:
                    batch.append(transformed)
                if len(batch) >= self.batch_size:
                    await self._flush(batch, stats)
                    batch = []
            except Exception as exc:  # pragma: no cover
                stats.failed += 1
                stats.errors.append(str(exc))
        if batch:
            await self._flush(batch, stats)
        stats.elapsed_seconds = max(1e-6, time.perf_counter() - start)
        return stats

    async def _flush(self, batch: List[Dict[str, Any]], stats: StreamIngestStats) -> None:
        res = self.sink(batch)
        if inspect.isawaitable(res):
            await res
        stats.stored += len(batch)

