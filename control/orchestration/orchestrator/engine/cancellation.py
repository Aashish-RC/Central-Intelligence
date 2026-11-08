"""Cooperative Cancellation Token supporting immediate task halts and interrupt callbacks."""

import threading
from typing import Callable, List, Optional


class PlanCancelledException(Exception):
    """Raised when an operation is aborted by a cancellation token."""
    pass


class CancellationToken:
    """Thread-safe cooperative cancellation token."""

    def __init__(self):
        self._is_cancelled = False
        self._reason: Optional[str] = None
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[str], None]] = []

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._is_cancelled

    @property
    def reason(self) -> Optional[str]:
        with self._lock:
            return self._reason

    def cancel(self, reason: str = "Execution cancelled by operator") -> None:
        """Trigger cancellation and invoke any registered cleanup callbacks."""
        with self._lock:
            if self._is_cancelled:
                return
            self._is_cancelled = True
            self._reason = reason

        for cb in self._callbacks:
            try:
                cb(reason)
            except Exception:
                pass

    def check(self) -> None:
        """Raises PlanCancelledException if cancellation has been requested."""
        if self.is_cancelled:
            raise PlanCancelledException(self.reason or "Execution cancelled")

    def register_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback to be notified immediately when cancelled."""
        with self._lock:
            if self._is_cancelled:
                # Already cancelled, trigger callback immediately
                callback(self._reason or "Execution cancelled")
            else:
                self._callbacks.append(callback)
