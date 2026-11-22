#!/usr/bin/env python3
"""Central Intelligence — Tier-3 On-Demand Wake/Sleep Controller (Task A13).

Manages scale-to-zero and on-demand spinning for heavyweight / optional services
(Qdrant, Memgraph, Phoenix, Meilisearch, Ollama, LibreChat).
Mitigates cold-start latency with prewarm-on-login and prewarm-on-schedule hooks.
"""

from __future__ import annotations

import datetime
import json
import threading
import time
from typing import Any, Callable, Dict, List, Optional


class OnDemandServiceRecord:
    """State record for a Tier 3 managed service."""

    def __init__(self, name: str, port: int, idle_timeout_s: int = 300):
        self.name = name
        self.port = port
        self.idle_timeout_s = idle_timeout_s
        self.status = "stopped"  # stopped, warming, running, draining
        self.last_active_at = time.time()
        self.active_connections = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "port": self.port,
            "status": self.status,
            "idle_timeout_s": self.idle_timeout_s,
            "active_connections": self.active_connections,
            "seconds_idle": int(time.time() - self.last_active_at),
        }


class OnDemandController:
    """Orchestrates Tier 3 scale-to-zero and wake-up workflows."""

    def __init__(self):
        self.services: Dict[str, OnDemandServiceRecord] = {
            "qdrant": OnDemandServiceRecord("qdrant", 6333, idle_timeout_s=300),
            "memgraph": OnDemandServiceRecord("memgraph", 7687, idle_timeout_s=300),
            "phoenix": OnDemandServiceRecord("phoenix", 6006, idle_timeout_s=300),
            "meilisearch": OnDemandServiceRecord("meilisearch", 7700, idle_timeout_s=300),
            "ollama": OnDemandServiceRecord("ollama", 11434, idle_timeout_s=600),
            "librechat": OnDemandServiceRecord("librechat", 3080, idle_timeout_s=300),
        }
        self._lock = threading.Lock()

    def record_activity(self, service_name: str) -> None:
        """Mark service as actively utilized."""
        with self._lock:
            if service_name in self.services:
                self.services[service_name].last_active_at = time.time()
                if self.services[service_name].status == "stopped":
                    self.services[service_name].status = "running"

    def prewarm_on_login(self, user_id: str, targets: Optional[List[str]] = None) -> List[str]:
        """Prewarm selected on-demand backends ahead of user requests."""
        prewarmed = []
        target_list = targets or ["qdrant", "ollama"]
        with self._lock:
            for name in target_list:
                if name in self.services:
                    svc = self.services[name]
                    if svc.status != "running":
                        svc.status = "warming"
                        svc.last_active_at = time.time()
                        prewarmed.append(name)
        return prewarmed

    def prewarm_on_schedule(self, schedule_name: str, targets: List[str]) -> List[str]:
        """Scheduled prewarming rule (e.g. prior to daily analytical runs)."""
        return self.prewarm_on_login(user_id=f"schedule:{schedule_name}", targets=targets)

    def check_idle_drain(self) -> List[str]:
        """Inspect all running services and trigger idle drain/sleep for timed-out instances."""
        now = time.time()
        drained = []
        with self._lock:
            for name, svc in self.services.items():
                if svc.status in ("running", "warming"):
                    idle_time = now - svc.last_active_at
                    if idle_time >= svc.idle_timeout_s and svc.active_connections == 0:
                        svc.status = "stopped"
                        drained.append(name)
        return drained

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {name: svc.to_dict() for name, svc in self.services.items()}


if __name__ == "__main__":
    controller = OnDemandController()
    print("[on-demand] Initial state:")
    print(json.dumps(controller.get_status(), indent=2))

    print("\n[on-demand] Testing prewarm on login:")
    warmed = controller.prewarm_on_login(user_id="user-123")
    print(f"Prewarmed services: {warmed}")

    print("\n[on-demand] State after prewarm:")
    print(json.dumps(controller.get_status(), indent=2))
