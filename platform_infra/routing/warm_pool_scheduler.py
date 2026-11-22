#!/usr/bin/env python3
"""Central Intelligence — Tier-2 Warm Pool Scheduler & Cron Controller (Task A12).

Controls scheduled scaling for Tier 2 services (Temporal, Lago, Langfuse):
- Active Window (06:00 – 22:00 tenant-local time): Scale to 1 replica (Warm).
- Off-Hours Window (22:00 – 06:00): Scale to 0 replicas (Sleep / Cost Drop).
Background jobs and events queue safely in PostgreSQL/Valkey during sleep.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from typing import Dict, List

TIER_2_SERVICES = ["temporal", "lago", "lago-worker"]
ACTIVE_START_HOUR = 6
ACTIVE_END_HOUR = 22


def get_current_tenant_hour() -> int:
    """Return local hour for the tenant timezone (default local system time)."""
    return datetime.datetime.now().hour


def is_active_window(hour: int | None = None) -> bool:
    """Check if current time is within 06:00 - 22:00 active warm window."""
    h = get_current_tenant_hour() if hour is None else hour
    return ACTIVE_START_HOUR <= h < ACTIVE_END_HOUR


def evaluate_tier_2_state(hour: int | None = None) -> Dict[str, str]:
    """Evaluate target replica state for Tier-2 services."""
    active = is_active_window(hour)
    target_replicas = 1 if active else 0
    state = "active_warm" if active else "sleeping_idle"

    status = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tenant_hour": get_current_tenant_hour() if hour is None else hour,
        "is_active_window": active,
        "target_replicas": target_replicas,
        "state": state,
        "services": {svc: target_replicas for svc in TIER_2_SERVICES},
    }
    return status


def apply_warm_pool_schedule(dry_run: bool = True) -> Dict[str, str]:
    """Execute docker compose scale command or update warm pool state."""
    status = evaluate_tier_2_state()
    target_replicas = status["target_replicas"]
    print(f"[warm-pool] Status: {status['state']} (Target replicas: {target_replicas})")

    if not dry_run:
        for svc in TIER_2_SERVICES:
            cmd = ["docker", "compose", "scale", f"{svc}={target_replicas}"]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"[warm-pool] Scaled {svc} to {target_replicas}")
            except Exception as e:
                print(f"[warm-pool] Scale command for {svc} skipped: {e}")

    return status


if __name__ == "__main__":
    res = apply_warm_pool_schedule(dry_run=True)
    print(json.dumps(res, indent=2))
