"""
Pheonix Resource Optimizer Signals
Abstract interface and implementations for reading host load and provider headroom.
"""

from abc import ABC, abstractmethod
from typing import Callable, Dict, Optional
import psutil

from ..models import ResourceSignals


class SignalSource(ABC):
    """Interface for acquiring system load and provider rate-limit signals."""

    @abstractmethod
    def get_signals(self) -> ResourceSignals:
        """Collect current resource and headroom signals."""
        pass


class PsutilSignalSource(SignalSource):
    """Default signal source querying host OS metrics via psutil."""

    def __init__(
        self,
        provider_headroom_provider: Optional[Callable[[], Dict[str, float]]] = None,
        queue_depth_provider: Optional[Callable[[], int]] = None,
    ):
        self._provider_headroom_provider = provider_headroom_provider
        self._queue_depth_provider = queue_depth_provider

    def get_signals(self) -> ResourceSignals:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        headroom = self._provider_headroom_provider() if self._provider_headroom_provider else {}
        queue_depth = self._queue_depth_provider() if self._queue_depth_provider else 0
        return ResourceSignals(
            cpu_percent=float(cpu),
            ram_percent=float(mem),
            queue_depth=queue_depth,
            provider_headroom=headroom,
        )


class FakeSignalSource(SignalSource):
    """Test signal source allowing explicit injection and mutation of load signals."""

    def __init__(
        self,
        cpu_percent: float = 20.0,
        ram_percent: float = 30.0,
        gpu_percent: Optional[float] = None,
        queue_depth: int = 0,
        provider_headroom: Optional[Dict[str, float]] = None,
    ):
        self.cpu_percent = float(cpu_percent)
        self.ram_percent = float(ram_percent)
        self.gpu_percent = gpu_percent
        self.queue_depth = queue_depth
        self.provider_headroom = dict(provider_headroom or {})

    def get_signals(self) -> ResourceSignals:
        return ResourceSignals(
            cpu_percent=float(self.cpu_percent),
            ram_percent=float(self.ram_percent),
            gpu_percent=self.gpu_percent,
            queue_depth=self.queue_depth,
            provider_headroom=dict(self.provider_headroom),
        )
