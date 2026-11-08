"""Async Event Dispatcher and Pub/Sub EventBus for Agent Lifecycle."""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class EventType(str, Enum):
    AGENT_STARTED = "agent_started"
    AGENT_STEP = "agent_step"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    SUBAGENT_SPAWNED = "subagent_spawned"
    SUBAGENT_COMPLETED = "subagent_completed"
    MEMORY_RECALLED = "memory_recalled"
    MEMORY_STORED = "memory_stored"
    GUARDRAIL_INTERCEPTED = "guardrail_intercepted"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"


class AgentEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: EventType
    agent_id: str
    run_id: str
    step_number: Optional[int] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


EventHandler = Callable[[AgentEvent], Coroutine[Any, Any, None]]


class EventBus:
    """Thread-safe and async event bus for agent lifecycle monitoring."""

    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._history: List[AgentEvent] = []
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: EventType | str, handler: EventHandler) -> None:
        """Register an async callback for a specific event type or '*' for all."""
        key = str(event_type)
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(handler)

    def unsubscribe(self, event_type: EventType | str, handler: EventHandler) -> None:
        """Remove a previously registered handler."""
        key = str(event_type)
        if key in self._subscribers and handler in self._subscribers[key]:
            self._subscribers[key].remove(handler)

    async def publish(self, event: AgentEvent) -> None:
        """Publish an event to all registered subscribers."""
        async with self._lock:
            self._history.append(event)
            # Cap history to last 10,000 events to prevent unbounded memory growth
            if len(self._history) > 10000:
                self._history.pop(0)

        # Notify exact subscribers
        exact_key = str(event.event_type)
        listeners = list(self._subscribers.get(exact_key, []))
        # Notify wildcard subscribers
        listeners.extend(self._subscribers.get("*", []))

        tasks = [asyncio.create_task(listener(event)) for listener in listeners]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_history(self, run_id: Optional[str] = None) -> List[AgentEvent]:
        """Retrieve recorded events, optionally filtered by run_id."""
        if run_id:
            return [e for e in self._history if e.run_id == run_id]
        return list(self._history)

    def clear(self) -> None:
        """Clear all event history and subscribers."""
        self._history.clear()
        self._subscribers.clear()


# Global shared instance
default_event_bus = EventBus()
