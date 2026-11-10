"""Hot-Swap Without Downtime (L16 Compute - Task 16.05).

Provides zero-downtime model hot-swapping.
When a hot-swap is triggered (e.g., swapping Claude -> GPT-4):
- All new incoming requests are immediately routed to the new model.
- Existing in-flight requests running against the previous model finish
  gracefully without interruption or request drops.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class SwapEvent:
    """Audit record for a model swap event."""
    from_model: str
    to_model: str
    swapped_at: float = field(default_factory=time.time)
    drained_at: Optional[float] = None
    in_flight_during_swap: int = 0


@dataclass
class ModelExecutionHandle:
    """Handle holding lease to a model invocation during execution."""
    request_id: str
    model_id: str
    manager: ModelHotSwapManager
    started_at: float = field(default_factory=time.time)


class ModelHotSwapManager:
    """Manages active inference target with seamless zero-downtime hot swapping."""

    def __init__(self, initial_model: str = "claude-3-7-sonnet") -> None:
        self._lock = threading.Lock()
        self._active_model: str = initial_model
        # model_id -> set of active request_ids
        self._in_flight: Dict[str, Set[str]] = {initial_model: set()}
        self._swap_history: List[SwapEvent] = []
        # Total requests serviced per model
        self._serviced_counts: Dict[str, int] = {initial_model: 0}

    @property
    def active_model(self) -> str:
        """Currently designated active model for new requests."""
        with self._lock:
            return self._active_model

    def acquire(self, request_id: str) -> ModelExecutionHandle:
        """Acquire an execution lease for a new request bound to the current active model."""
        with self._lock:
            target_model = self._active_model
            if target_model not in self._in_flight:
                self._in_flight[target_model] = set()
            self._in_flight[target_model].add(request_id)
            self._serviced_counts[target_model] = self._serviced_counts.get(target_model, 0) + 1

        return ModelExecutionHandle(
            request_id=request_id,
            model_id=target_model,
            manager=self,
        )

    def release(self, handle: ModelExecutionHandle) -> None:
        """Release an execution lease when request completes."""
        with self._lock:
            if handle.model_id in self._in_flight:
                self._in_flight[handle.model_id].discard(handle.request_id)

    def execute(self, request_id: str, executor: Callable[[str], Any]) -> Any:
        """Execute request under hot-swap lease protection with zero dropped requests."""
        handle = self.acquire(request_id)
        try:
            return executor(handle.model_id)
        finally:
            self.release(handle)

    def hot_swap(self, new_model: str) -> SwapEvent:
        """Atomically swap the active model.

        New requests instantly route to new_model.
        In-flight requests continue executing against old_model.
        """
        with self._lock:
            old_model = self._active_model
            if old_model == new_model:
                logger.info("Hot-swap target is already active model: %s", new_model)
                return SwapEvent(from_model=old_model, to_model=new_model, in_flight_during_swap=0)

            in_flight_count = len(self._in_flight.get(old_model, set()))
            self._active_model = new_model

            if new_model not in self._in_flight:
                self._in_flight[new_model] = set()

            event = SwapEvent(
                from_model=old_model,
                to_model=new_model,
                in_flight_during_swap=in_flight_count,
            )
            self._swap_history.append(event)
            logger.info(
                "Hot-swapped active model from '%s' to '%s'. In-flight on previous: %d",
                old_model,
                new_model,
                in_flight_count,
            )
            return event

    def get_in_flight_count(self, model_id: Optional[str] = None) -> int:
        """Return number of currently running requests for a model (or all)."""
        with self._lock:
            if model_id:
                return len(self._in_flight.get(model_id, set()))
            return sum(len(s) for s in self._in_flight.values())

    def get_serviced_count(self, model_id: str) -> int:
        """Return total requests ever completed/acquired by model."""
        with self._lock:
            return self._serviced_counts.get(model_id, 0)
