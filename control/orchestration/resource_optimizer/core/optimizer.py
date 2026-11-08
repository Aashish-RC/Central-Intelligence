"""
Pheonix Resource Optimizer Core
Coordinates adaptive concurrency bounds, system resource safety, and task scheduling.
"""

import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional, Tuple, Union

from ..models import (
    Decision,
    ResourceOptimizerConfig,
    ResourceSignals,
    TaskDescriptor,
)
from .signals import PsutilSignalSource, SignalSource


class ResourceOptimizer:
    """
    Adaptive concurrency controller that monitors host vitals and rate-limit headroom.
    Guarantees thread-safe, deterministic decisions and prevents host lockups.
    """

    def __init__(
        self,
        signal_source: Optional[SignalSource] = None,
        clock: Optional[Callable[[], float]] = None,
        config: Optional[ResourceOptimizerConfig] = None,
        device_profile: Optional[Any] = None,
    ):
        self.signal_source = signal_source or PsutilSignalSource()
        self._clock = clock if clock is not None else time.monotonic
        self.config = config or ResourceOptimizerConfig()

        # Set max cap from device_profile if provided
        if device_profile is not None:
            if hasattr(device_profile, "logical_cores") and device_profile.logical_cores:
                self.max_cap = int(device_profile.logical_cores)
            elif hasattr(device_profile, "physical_cores") and device_profile.physical_cores:
                self.max_cap = int(device_profile.physical_cores)
            else:
                self.max_cap = self.config.max_cap
        else:
            self.max_cap = self.config.max_cap

        self.concurrency_cap = min(self.config.initial_cap, self.max_cap)
        self._consecutive_healthy: int = 0
        self._active_tasks: Dict[str, float] = {}  # task_id -> lease_start_timestamp
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self._last_status: str = f"Operating normally with concurrency cap {self.concurrency_cap}."

    @property
    def active_count(self) -> int:
        """Current number of active acquired tasks."""
        with self._lock:
            self._reap_stale_leases()
            return len(self._active_tasks)

    def _extract_task_info(self, task: Any) -> Tuple[str, Optional[str]]:
        """Extract unique task_id and optional provider string from any task representation."""
        if task is None:
            return f"task_{uuid.uuid4().hex[:8]}", None
        if isinstance(task, str):
            return task, None
        if isinstance(task, TaskDescriptor):
            return task.task_id, task.provider
        if hasattr(task, "id"):
            provider = None
            if hasattr(task, "params") and isinstance(task.params, dict):
                provider = task.params.get("provider") or task.params.get("model_provider")
            return str(getattr(task, "id")), provider
        return str(task), None

    def _reap_stale_leases(self) -> None:
        """Reclaim slot leases that have exceeded lease_timeout_seconds to prevent deadlocks."""
        now = self._clock()
        stale = [
            tid
            for tid, acquired_at in self._active_tasks.items()
            if (now - acquired_at) >= self.config.lease_timeout_seconds
        ]
        for tid in stale:
            del self._active_tasks[tid]
        if stale:
            self._cond.notify_all()

    def acquire(self, task: Any = None) -> Decision:
        """
        Evaluate current system signals, adapt concurrency cap, and decide whether to allow,
        delay, or reject task execution.
        """
        task_id, provider = self._extract_task_info(task)

        with self._lock:
            now = self._clock()
            self._reap_stale_leases()

            signals = self.signal_source.get_signals()

            # Detect pressure
            is_cpu_high = signals.cpu_percent > self.config.cpu_threshold_percent
            is_ram_high = signals.ram_percent > self.config.ram_threshold_percent

            # Check provider headroom
            low_headroom_val = None
            low_headroom_provider = None
            if signals.provider_headroom:
                if provider and provider in signals.provider_headroom:
                    val = signals.provider_headroom[provider]
                    if val < self.config.provider_headroom_threshold:
                        low_headroom_val = val
                        low_headroom_provider = provider
                else:
                    for prov, val in signals.provider_headroom.items():
                        if val < self.config.provider_headroom_threshold:
                            low_headroom_val = val
                            low_headroom_provider = prov
                            break

            is_provider_constrained = low_headroom_val is not None

            # Adapt concurrency cap
            if is_cpu_high or is_ram_high or is_provider_constrained:
                self.concurrency_cap = max(1, self.concurrency_cap // 2)
                self._consecutive_healthy = 0
            else:
                self._consecutive_healthy += 1
                if self._consecutive_healthy >= self.config.healthy_checks_threshold:
                    self.concurrency_cap = min(self.concurrency_cap + 1, self.max_cap)
                    self._consecutive_healthy = 0

            # 1. Provider headroom delay
            if is_provider_constrained:
                self._last_status = "Slowing down to protect provider rate limits."
                prov_label = f"Provider '{low_headroom_provider}'" if low_headroom_provider else "Provider"
                return Decision(
                    action="delay",
                    concurrency_cap=self.concurrency_cap,
                    delay_seconds=self.config.default_delay_seconds,
                    reason=f"{prov_label} rate limit headroom is critically low ({low_headroom_val:.1%}).",
                )

            # 2. Concurrency cap exhaustion
            if len(self._active_tasks) >= self.concurrency_cap:
                if is_cpu_high or is_ram_high:
                    self._last_status = "Slowing down to protect your device."
                    reason = (
                        f"System under heavy load (CPU {signals.cpu_percent:.1f}%, RAM {signals.ram_percent:.1f}%) "
                        f"and concurrency cap of {self.concurrency_cap} reached."
                    )
                else:
                    self._last_status = f"Throttling at concurrency cap {self.concurrency_cap} to maintain stability."
                    reason = f"Concurrency cap ({self.concurrency_cap}) reached with {len(self._active_tasks)} active tasks."

                return Decision(
                    action="delay",
                    concurrency_cap=self.concurrency_cap,
                    delay_seconds=self.config.default_delay_seconds,
                    reason=reason,
                )

            # 3. Allow execution
            self._active_tasks[task_id] = now
            if is_cpu_high or is_ram_high:
                self._last_status = "Slowing down to protect your device."
                reason = "Execution granted under reduced adaptive cap due to elevated host load."
            else:
                self._last_status = f"Operating normally with concurrency cap {self.concurrency_cap}."
                reason = "System resources and concurrency limits are within healthy bounds."

            return Decision(
                action="allow",
                concurrency_cap=self.concurrency_cap,
                delay_seconds=0.0,
                reason=reason,
            )

    def acquire_blocking(self, task: Any = None, timeout: Optional[float] = None) -> Decision:
        """Block until execution capacity is granted or timeout expires."""
        start_time = self._clock()
        while True:
            decision = self.acquire(task)
            if decision.action == "allow" or decision.action == "reject":
                return decision

            if timeout is not None:
                elapsed = self._clock() - start_time
                if elapsed >= timeout:
                    return Decision(
                        action="reject",
                        concurrency_cap=self.concurrency_cap,
                        delay_seconds=0.0,
                        reason=f"Acquisition timed out after {timeout:.2f} seconds.",
                    )

            sleep_duration = decision.delay_seconds if decision.delay_seconds > 0 else 0.05
            with self._cond:
                self._cond.wait(timeout=sleep_duration)

    def release(self, task: Any = None) -> None:
        """Release acquired execution slot for the task and notify waiting workers."""
        task_id, _ = self._extract_task_info(task)
        with self._lock:
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]
            elif self._active_tasks:
                # If exact ID not matched, release oldest active lease to prevent leak
                oldest_id = min(self._active_tasks, key=self._active_tasks.get)
                del self._active_tasks[oldest_id]
            self._cond.notify_all()

    def status_message(self) -> str:
        """One readable line describing the current operating health and throttling status."""
        with self._lock:
            # Refresh status if current signals indicate pressure
            signals = self.signal_source.get_signals()
            if (
                signals.cpu_percent > self.config.cpu_threshold_percent
                or signals.ram_percent > self.config.ram_threshold_percent
            ):
                return "Slowing down to protect your device."
            if signals.provider_headroom and any(
                v < self.config.provider_headroom_threshold for v in signals.provider_headroom.values()
            ):
                return "Slowing down to protect provider rate limits."
            return self._last_status
