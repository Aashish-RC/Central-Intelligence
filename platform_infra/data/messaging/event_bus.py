"""Durable Priority Event Bus with Dead-Letter & Retry Handling (L15 Features 15.27, 15.28)."""

from __future__ import annotations

import asyncio
import heapq
import inspect
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol, Tuple

from control.safety.production_guard import is_production, require_live_adapter

logger = logging.getLogger(__name__)

EventHandler = Callable[[Dict[str, Any]], Any]


class EventBusBackend(Protocol):
    """Protocol implemented by EventBus storage/broker backends."""

    async def produce(self, topic: str, event: Dict[str, Any], priority: int = 0) -> str: ...

    async def consume(
        self,
        topic: str,
        handler: EventHandler,
        priority: int = 0,
    ) -> int: ...


@dataclass(order=True)
class _QueuedEnvelope:
    sort_key: Tuple[int, int]
    event_id: str = field(compare=False)
    topic: str = field(compare=False)
    payload: Dict[str, Any] = field(compare=False)
    priority: int = field(compare=False)
    timestamp: float = field(compare=False)
    attempts: int = field(default=0, compare=False)


class InMemoryEventBusBackend:
    """In-memory durable priority queue backend for hermetic tests and local dev."""

    def __init__(self) -> None:
        self._seq: int = 0
        self._queues: Dict[str, List[_QueuedEnvelope]] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {}

    async def produce(self, topic: str, event: Dict[str, Any], priority: int = 0) -> str:
        self._seq += 1
        event_id = str(event.get("event_id") or f"evt-{uuid.uuid4().hex[:12]}")
        envelope_payload = dict(event)
        envelope_payload.setdefault("event_id", event_id)
        envelope_payload.setdefault("priority", priority)
        envelope_payload.setdefault("timestamp", time.time())
        env = _QueuedEnvelope(
            sort_key=(-priority, self._seq),
            event_id=event_id,
            topic=topic,
            payload=envelope_payload,
            priority=priority,
            timestamp=float(envelope_payload["timestamp"]),
        )
        heapq.heappush(self._queues.setdefault(topic, []), env)
        self._history.setdefault(topic, []).append(envelope_payload)
        return event_id

    async def consume(
        self,
        topic: str,
        handler: EventHandler,
        priority: int = 0,
        max_retries: int = 2,
        dlq_callback: Optional[Callable[[str, Dict[str, Any], str], Awaitable[None]]] = None,
    ) -> int:
        queue = self._queues.get(topic, [])
        processed = 0
        deferred: List[_QueuedEnvelope] = []
        while queue:
            env = heapq.heappop(queue)
            if env.priority < priority:
                deferred.append(env)
                continue
            last_err: Optional[Exception] = None
            delivered = False
            for _ in range(max_retries + 1):
                env.attempts += 1
                try:
                    res = handler(env.payload)
                    if inspect.isawaitable(res):
                        await res
                    delivered = True
                    processed += 1
                    break
                except Exception as exc:  # pragma: no cover - verified by retry/DLQ tests
                    last_err = exc
            if not delivered and dlq_callback is not None:
                await dlq_callback(topic, env.payload, str(last_err or "handler failed"))
        for item in deferred:
            heapq.heappush(queue, item)
        return processed

    def list_events(self, topic: str) -> List[Dict[str, Any]]:
        return list(self._history.get(topic, []))


class EventBus:
    """Pub/sub event bus with priority queues, retries, and dead-letter routing (15.27, 15.28)."""

    def __init__(
        self,
        backend: Optional[Any] = None,
        max_retries: int = 2,
        adapter_mode: Optional[str] = None,
    ) -> None:
        has_live = backend is not None and not isinstance(backend, InMemoryEventBusBackend)
        if adapter_mode is not None:
            mode = adapter_mode.strip().lower()
            if is_production() and mode != "live":
                require_live_adapter("EVENT_BUS")
            self.adapter_mode = mode
        elif has_live:
            self.adapter_mode = "live"
        else:
            self.adapter_mode = require_live_adapter("EVENT_BUS")
        self.backend = backend if backend is not None else InMemoryEventBusBackend()
        self.max_retries = max_retries
        self._subscriptions: Dict[str, List[Tuple[int, EventHandler]]] = {}

    async def publish(self, topic: str, event: Dict[str, Any], priority: int = 0) -> str:
        """Publish an event to ``topic`` with integer priority (higher = delivered earlier)."""
        event_id = await self.backend.produce(topic, event, priority=priority)
        for min_prio, handler in self._subscriptions.get(topic, []):
            if priority >= min_prio:
                await self.drain(topic, handler, priority=min_prio)
        return event_id

    async def subscribe(
        self,
        topic: str,
        handler: EventHandler,
        priority: int = 0,
        drain_existing: bool = True,
    ) -> None:
        """Register ``handler`` for ``topic`` and optionally drain queued messages."""
        self._subscriptions.setdefault(topic, []).append((priority, handler))
        if drain_existing:
            await self.drain(topic, handler, priority=priority)

    async def drain(self, topic: str, handler: EventHandler, priority: int = 0) -> int:
        """Deliver queued messages for ``topic`` meeting ``priority``, routing failures to DLQ."""
        if isinstance(self.backend, InMemoryEventBusBackend):
            return await self.backend.consume(
                topic,
                handler,
                priority=priority,
                max_retries=self.max_retries,
                dlq_callback=self.dead_letter,
            )
        return await self.backend.consume(topic, handler, priority=priority)

    async def dead_letter(self, topic: str, event: Dict[str, Any], reason: str) -> str:
        """Send an undeliverable event to ``{topic}.dlq``."""
        dlq_topic = f"{topic}.dlq"
        return await self.backend.produce(
            dlq_topic,
            {"event": event, "reason": reason, "failed_at": time.time()},
            priority=0,
        )

    def inspect_dlq(self, topic: str) -> List[Dict[str, Any]]:
        """Inspect dead-letter records for ``topic`` when using in-memory backend."""
        if isinstance(self.backend, InMemoryEventBusBackend):
            return self.backend.list_events(f"{topic}.dlq")
        return []

