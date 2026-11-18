#!/usr/bin/env python3
"""
CLI entrypoint and runner for Central Intelligence Production Service Watchdog (Stage S4.8).

Usage:
    python scripts/run_service_watchdog.py [--verify-once] [--interval 10]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from platform_infra.compute.health.service_watchdog import (
    ServiceWatchdog,
    ServiceProbeConfig,
    ServiceHealthStatus,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Watchdog] %(message)s",
)
logger = logging.getLogger("Watchdog")


def build_default_watchdog(interval_s: float = 10.0, auto_heal: bool = True) -> ServiceWatchdog:
    wd = ServiceWatchdog(check_interval_s=interval_s, auto_heal_enabled=auto_heal)

    # 1. PostgreSQL Relational State
    wd.register_service(
        ServiceProbeConfig(
            service_name="postgres",
            probe_type="tcp",
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            container_name="central-supabase-db",
        )
    )

    # 2. Valkey Ephemeral Cache
    wd.register_service(
        ServiceProbeConfig(
            service_name="valkey",
            probe_type="tcp",
            host=os.getenv("VALKEY_HOST", "127.0.0.1"),
            port=int(os.getenv("VALKEY_PORT", "6379")),
            container_name="central-valkey",
        )
    )

    # 3. Qdrant Vector Search
    wd.register_service(
        ServiceProbeConfig(
            service_name="qdrant",
            probe_type="tcp",
            host=os.getenv("QDRANT_HOST", "127.0.0.1"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            container_name="central-qdrant",
        )
    )

    # 4. Temporal Durable Workflow
    wd.register_service(
        ServiceProbeConfig(
            service_name="temporal",
            probe_type="tcp",
            host=os.getenv("TEMPORAL_HOST", "127.0.0.1"),
            port=int(os.getenv("TEMPORAL_PORT", "7233")),
            container_name="central-temporal",
        )
    )

    return wd


def main():
    parser = argparse.ArgumentParser(description="Central Intelligence Service Watchdog")
    parser.add_argument("--verify-once", action="store_true", help="Run a single probe sweep and output status JSON")
    parser.add_argument("--interval", type=float, default=10.0, help="Check interval in seconds")
    parser.add_argument("--no-auto-heal", action="store_true", help="Disable automatic remediation")
    args = parser.parse_args()

    wd = build_default_watchdog(interval_s=args.interval, auto_heal=not args.no_auto_heal)

    if args.verify_once:
        logger.info("Executing diagnostic probe sweep...")
        results = wd.run_all_probes()
        logger.info("Diagnostic Probe Results: %s", results)
        statuses = wd.get_all_statuses()
        for name, data in statuses.items():
            logger.info("  [%s] Status: %s | Failures: %d | Latency: %.1fms", name, data["status"], data["consecutive_failures"], data["last_latency_ms"])
        sys.exit(0)

    logger.info("Starting Watchdog daemon loop (interval: %.1fs)...", args.interval)
    try:
        while True:
            wd.run_all_probes()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Watchdog daemon stopped by user.")


if __name__ == "__main__":
    main()
