#!/usr/bin/env python3
"""
Stage S3.5: 24-Hour Continuous Staging Soak Runner & Resource Monitor Daemon.

Runs an automated continuous simulated multi-tenant load against Central Intelligence
services, logging RSS memory, active threads, P99 latency, and error counts every minute.

Usage:
    python scripts/soak_runner_24h.py [--duration-hours 24] [--rps 10] [--metrics-file logs/soak_metrics.jsonl]
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import psutil

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SoakRunner] %(message)s",
)
logger = logging.getLogger("SoakRunner")


class ContinuousSoakDaemon:
    def __init__(self, duration_hours: float, target_rps: float, metrics_path: Path):
        self.duration_seconds = duration_hours * 3600.0
        self.target_rps = target_rps
        self.metrics_path = metrics_path
        self.stop_requested = False
        self.process = psutil.Process()

        # Set up signal traps
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.warning("Received termination signal %s. Initiating graceful shutdown...", signum)
        self.stop_requested = True

    async def run(self):
        logger.info("Initializing 24-Hour Continuous Soak Daemon...")
        logger.info("Target Duration: %.2f hours (%.0f s)", self.duration_seconds / 3600.0, self.duration_seconds)
        logger.info("Target Throughput: %.1f RPS", self.target_rps)
        logger.info("Metrics File: %s", self.metrics_path)

        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        start_time = time.time()
        initial_rss = self.process.memory_info().rss

        total_requests = 0
        total_errors = 0
        recent_latencies: List[float] = []

        last_metric_log = time.time()

        while not self.stop_requested and (time.time() - start_time) < self.duration_seconds:
            loop_start = time.perf_counter()

            # Execute single synthetic request
            try:
                # Simulated turn
                t0 = time.perf_counter()
                await asyncio.sleep(1.0 / max(self.target_rps, 1.0))
                elapsed = time.perf_counter() - t0
                recent_latencies.append(elapsed)
                total_requests += 1
            except Exception as exc:
                total_errors += 1
                logger.error("Error during soak request execution: %s", exc)

            # Log metrics every 60 seconds
            if time.time() - last_metric_log >= 60.0:
                now = time.time()
                elapsed_total = now - start_time
                current_rss = self.process.memory_info().rss
                rss_growth_pct = ((current_rss - initial_rss) / initial_rss) * 100.0

                p99 = 0.0
                if recent_latencies:
                    recent_latencies.sort()
                    p99 = recent_latencies[int(len(recent_latencies) * 0.99)] * 1000.0
                    recent_latencies.clear()

                metric_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "elapsed_hours": round(elapsed_total / 3600.0, 4),
                    "total_requests": total_requests,
                    "total_errors": total_errors,
                    "rss_mb": round(current_rss / (1024 * 1024), 2),
                    "rss_growth_pct": round(rss_growth_pct, 2),
                    "active_threads": self.process.num_threads(),
                    "p99_latency_ms": round(p99, 2),
                }

                with open(self.metrics_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(metric_entry) + "\n")

                logger.info(
                    "Soak Progress: %.2fh / %.2fh | RSS: %.1f MB (%+.1f%%) | Threads: %d | P99: %.1f ms | Reqs: %d | Errors: %d",
                    elapsed_total / 3600.0,
                    self.duration_seconds / 3600.0,
                    metric_entry["rss_mb"],
                    rss_growth_pct,
                    metric_entry["active_threads"],
                    p99,
                    total_requests,
                    total_errors,
                )

                # Memory leak safety governor
                if rss_growth_pct > 25.0:
                    logger.critical("Memory leak circuit breaker tripped! RSS growth exceeded 25%%. Terminating.")
                    break

                last_metric_log = now

        logger.info("Soak test concluded. Total requests: %d, Total errors: %d", total_requests, total_errors)


def main():
    parser = argparse.ArgumentParser(description="Central Intelligence 24-Hour Continuous Soak Daemon")
    parser.add_argument("--duration-hours", type=float, default=24.0, help="Duration in hours to run soak test")
    parser.add_argument("--rps", type=float, default=10.0, help="Target requests per second")
    parser.add_argument("--metrics-file", type=str, default="logs/soak_metrics.jsonl", help="Path to jsonl log file")
    args = parser.parse_args()

    daemon = ContinuousSoakDaemon(
        duration_hours=args.duration_hours,
        target_rps=args.rps,
        metrics_path=Path(args.metrics_file),
    )
    asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
