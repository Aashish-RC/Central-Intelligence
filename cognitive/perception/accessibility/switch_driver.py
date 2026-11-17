"""
Physical Switch Access Hardware Driver Interface (Layer 1: Perception, Task 1.10; Feature 1.46).

Provides hardware abstraction for single-switch and dual-switch assistive hardware (sip-and-puff, head switches,
button switches) for motor-impaired accessibility.
Physical switch hardware connection is deferred to physical accessibility testing packs.
"""

from __future__ import annotations

import collections
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("cognitive.perception.accessibility.switch")


class SwitchAction(str, Enum):
    PRESS = "press"
    LONG_PRESS = "long_press"
    DOUBLE_PRESS = "double_press"
    RELEASE = "release"
    STEP_SCAN = "step_scan"


@dataclass
class SwitchEvent:
    """An event dispatched by an assistive switch device."""
    switch_id: str
    action: SwitchAction = SwitchAction.PRESS
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0


class SwitchAccessDriver:
    """
    Physical switch hardware abstraction driver.
    Supports physical switch mode (deferred to physical test packs) and synthetic event queue emulation mode.
    """

    def __init__(self, port: Optional[str] = None, mode: str = "physical") -> None:
        self.port = port
        self.mode = mode
        self.is_connected = False
        self._event_queue: Deque[SwitchEvent] = collections.deque()
        self._last_event_time: float = 0.0
        self.debounce_ms: float = 50.0

    def enable_synthetic_mode(self) -> None:
        """Switch driver to synthetic software emulation mode."""
        self.mode = "synthetic"

    def connect(self, device_port: Optional[str] = None) -> Dict[str, Any]:
        """Attempts connection to an assistive switch device."""
        if self.mode == "physical":
            logger.info("Physical switch hardware connection requested on %s", device_port or self.port)
            return {
                "status": "not implemented",
                "device": "assistive_switch",
                "message": "Physical switch device access not implemented - hardware driver deferred to physical accessibility pack.",
            }

        self.is_connected = True
        return {
            "status": "connected",
            "device": "synthetic_assistive_switch",
            "port": device_port or self.port or "virtual_switch_port",
            "mode": "synthetic",
            "message": "Synthetic switch access driver connected.",
        }

    def dispatch_event(self, event: SwitchEvent) -> None:
        """Enqueue an event for polling with debounce suppression."""
        now = time.time()
        if (now - self._last_event_time) * 1000.0 >= self.debounce_ms:
            self._event_queue.append(event)
            self._last_event_time = now

    def poll_events(self) -> List[SwitchEvent]:
        """Polls switch events."""
        if self.mode == "physical":
            raise NotImplementedError("Physical switch device access not implemented.")

        events: List[SwitchEvent] = []
        while self._event_queue:
            events.append(self._event_queue.popleft())
        return events

    def simulate_event(self, action: SwitchAction | str = SwitchAction.PRESS, switch_id: str = "switch_1") -> SwitchEvent:
        """Software emulation helper for testing switch scan accessibility navigation."""
        act = SwitchAction(action) if isinstance(action, str) else action
        evt = SwitchEvent(switch_id=switch_id, action=act, timestamp=time.time())
        self.dispatch_event(evt)
        return evt
