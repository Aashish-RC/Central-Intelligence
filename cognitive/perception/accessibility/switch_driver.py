"""
Physical Switch Access Hardware Driver Interface (Layer 1: Perception, Task 1.10; Feature 1.46).

Interface for single-switch and dual-switch assistive hardware (sip-and-puff, head switches,
button switches) for motor-impaired accessibility. Hardware driver implementation deferred to physical pack.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cognitive.perception.accessibility.switch")


class SwitchAction(str, Enum):
    PRESS = "press"
    LONG_PRESS = "long_press"
    DOUBLE_PRESS = "double_press"
    RELEASE = "release"
    STEP_SCAN = "step_scan"


@dataclass
class SwitchEvent:
    """An event dispatched by a physical assistive switch device."""
    switch_id: str
    action: SwitchAction = SwitchAction.PRESS
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0


class SwitchAccessDriver:
    """
    Physical switch hardware interface. Returns 'not implemented' for physical I/O (Task 1.10).
    """

    def __init__(self, port: Optional[str] = None) -> None:
        self.port = port
        self.is_connected = False

    def connect(self, device_port: Optional[str] = None) -> Dict[str, Any]:
        """Attempts connection to a physical assistive switch device."""
        logger.info("Physical switch hardware connection requested on %s", device_port or self.port)
        return {
            "status": "not implemented",
            "device": "assistive_switch",
            "message": "Physical switch device access not implemented - hardware driver deferred to physical accessibility pack.",
        }

    def poll_events(self) -> List[SwitchEvent]:
        """Polls raw physical switch events."""
        raise NotImplementedError("Physical switch device access not implemented.")

    def simulate_event(self, action: SwitchAction | str = SwitchAction.PRESS, switch_id: str = "switch_1") -> SwitchEvent:
        """Software emulation helper for testing switch scan accessibility navigation."""
        act = SwitchAction(action) if isinstance(action, str) else action
        return SwitchEvent(switch_id=switch_id, action=act, timestamp=time.time())

