#!/usr/bin/env python3
"""Central Intelligence — Tier-1 Router & Dynamic Tier-3 Route Controller (Task A11 / A13).

Lightweight (< 30 MB RSS) always-on HTTP route registry and proxy router.
Knows the routing topology for Tier 1 (Always-On), Tier 2 (Warm Pool),
and Tier 3 (On-Demand Scale-to-Zero) services.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict

ROUTE_TABLE: Dict[str, Dict[str, Any]] = {
    # Tier 1: Always-On Core
    "supabase-db": {"tier": 1, "port": 5432, "status": "always-on", "url": "http://supabase-db:5432"},
    "pgbouncer": {"tier": 1, "port": 6432, "status": "always-on", "url": "http://pgbouncer:6432"},
    "valkey": {"tier": 1, "port": 6379, "status": "always-on", "url": "http://valkey:6379"},
    "keycloak": {"tier": 1, "port": 8085, "status": "always-on", "url": "http://keycloak:8085"},
    "openfga": {"tier": 1, "port": 8080, "status": "always-on", "url": "http://openfga:8080"},
    "nats": {"tier": 1, "port": 4222, "status": "always-on", "url": "http://nats:4222"},
    "otel-collector": {"tier": 1, "port": 4318, "status": "always-on", "url": "http://otel-collector:4318"},

    # Tier 2: Warm Pool (06:00 - 22:00 active)
    "temporal": {"tier": 2, "port": 7233, "status": "warm", "url": "http://temporal:7233", "schedule": "06:00-22:00"},
    "lago": {"tier": 2, "port": 3000, "status": "warm", "url": "http://lago:3000", "schedule": "06:00-22:00"},

    # Tier 3: On-Demand (Scale to Zero)
    "qdrant": {"tier": 3, "port": 6333, "status": "on-demand", "url": "http://qdrant:6333", "idle_timeout_s": 300},
    "memgraph": {"tier": 3, "port": 7687, "status": "on-demand", "url": "http://memgraph:7687", "idle_timeout_s": 300},
    "phoenix": {"tier": 3, "port": 6006, "status": "on-demand", "url": "http://phoenix:6006", "idle_timeout_s": 300},
    "meilisearch": {"tier": 3, "port": 7700, "status": "on-demand", "url": "http://meilisearch:7700", "idle_timeout_s": 300},
    "ollama": {"tier": 3, "port": 11434, "status": "on-demand", "url": "http://ollama:11434", "idle_timeout_s": 600},
}


class TierRouterHandler(BaseHTTPRequestHandler):
    """Dynamic routing table and health controller."""

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/healthz", "/health"):
            self._send_json(200, {"status": "healthy", "service": "tier-router", "version": "1.0.0"})
        elif self.path == "/routes":
            self._send_json(200, {"total_routes": len(ROUTE_TABLE), "routes": ROUTE_TABLE})
        elif self.path.startswith("/routes/"):
            svc = self.path.split("/")[-1]
            if svc in ROUTE_TABLE:
                self._send_json(200, {"service": svc, "route": ROUTE_TABLE[svc]})
            else:
                self._send_json(404, {"error": f"Service '{svc}' not found in route table"})
        else:
            self._send_json(200, {"name": "Central Intelligence Tier Router", "docs": "/routes"})

    def do_POST(self) -> None:
        if self.path.startswith("/routes/wake/"):
            svc = self.path.split("/")[-1]
            if svc in ROUTE_TABLE:
                ROUTE_TABLE[svc]["status"] = "warming"
                self._send_json(200, {"action": "wake", "service": svc, "target_status": "warming"})
            else:
                self._send_json(404, {"error": f"Service '{svc}' not found"})
        elif self.path.startswith("/routes/sleep/"):
            svc = self.path.split("/")[-1]
            if svc in ROUTE_TABLE:
                ROUTE_TABLE[svc]["status"] = "sleeping"
                self._send_json(200, {"action": "sleep", "service": svc, "target_status": "sleeping"})
            else:
                self._send_json(404, {"error": f"Service '{svc}' not found"})
        else:
            self._send_json(400, {"error": "Unknown POST route"})

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Quiet logging


def start_router(host: str = "0.0.0.0", port: int = 8089) -> None:
    server = HTTPServer((host, port), TierRouterHandler)
    print(f"[tier-router] Listening on http://{host}:{port} with {len(ROUTE_TABLE)} routes.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    start_router()
