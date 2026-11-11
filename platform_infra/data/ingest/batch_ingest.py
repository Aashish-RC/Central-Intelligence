"""Scheduled Cron-Based Batch Data Ingestion (L15 Feature 15.33)."""

from __future__ import annotations

import inspect
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


def _cron_field_matches(expr_field: str, value: int, minimum: int, maximum: int) -> bool:
    for part in expr_field.split(","):
        step = 1
        base = part
        if "/" in part:
            base, step_str = part.split("/", 1)
            step = int(step_str)
            if step <= 0:
                raise ValueError(f"Invalid cron step: '{part}'")
        if base == "*":
            if (value - minimum) % step == 0:
                return True
        elif "-" in base:
            lo_s, hi_s = base.split("-", 1)
            lo, hi = int(lo_s), int(hi_s)
            if lo <= value <= hi and (value - lo) % step == 0:
                return True
        else:
            if int(base) == value:
                return True
    return False


def cron_matches(cron_expr: str, dt: datetime) -> bool:
    """Return True if a 5-field cron expression (m h dom mon dow) matches ``dt``."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Expected 5-field cron expression, got: '{cron_expr}'")
    minute, hour, dom, month, dow = parts
    # Convert Python weekday (Mon=0..Sun=6) to cron weekday (Sun=0..Sat=6)
    cron_dow = (dt.weekday() + 1) % 7
    return (
        _cron_field_matches(minute, dt.minute, 0, 59)
        and _cron_field_matches(hour, dt.hour, 0, 23)
        and _cron_field_matches(dom, dt.day, 1, 31)
        and _cron_field_matches(month, dt.month, 1, 12)
        and _cron_field_matches(dow, cron_dow, 0, 6)
    )


BatchJobFn = Callable[[], Any]


@dataclass
class BatchJob:
    """Registered scheduled batch ingestion job."""

    job_id: str
    name: str
    cron_expr: str
    runner: BatchJobFn
    enabled: bool = True
    last_run_at: Optional[datetime] = None
    run_count: int = 0


@dataclass
class BatchRunRecord:
    """Execution audit entry for a scheduled batch run."""

    job_id: str
    name: str
    ran_at: datetime
    status: str
    items_processed: int = 0
    error: Optional[str] = None


class BatchIngestScheduler:
    """Cron-driven scheduler for periodic batch ingestion jobs."""

    def __init__(self) -> None:
        self._jobs: Dict[str, BatchJob] = {}
        self.history: List[BatchRunRecord] = []

    def schedule(self, name: str, cron_expr: str, runner: BatchJobFn) -> BatchJob:
        # Validate cron syntax eagerly.
        cron_matches(cron_expr, datetime.now(timezone.utc))
        job_id = f"batch-{uuid.uuid4().hex[:10]}"
        job = BatchJob(job_id=job_id, name=name, cron_expr=cron_expr, runner=runner)
        self._jobs[job_id] = job
        return job

    def list_jobs(self) -> List[BatchJob]:
        return list(self._jobs.values())

    async def tick(self, now: Optional[datetime] = None) -> List[BatchRunRecord]:
        """Evaluate cron schedules at ``now`` and execute every matching enabled job."""
        current = now or datetime.now(timezone.utc)
        ran: List[BatchRunRecord] = []
        for job in self._jobs.values():
            if not job.enabled:
                continue
            if not cron_matches(job.cron_expr, current):
                continue
            try:
                res = job.runner()
                if inspect.isawaitable(res):
                    res = await res
                count = int(res) if isinstance(res, int) else 1
                rec = BatchRunRecord(
                    job_id=job.job_id,
                    name=job.name,
                    ran_at=current,
                    status="succeeded",
                    items_processed=count,
                )
            except Exception as exc:  # pragma: no cover
                rec = BatchRunRecord(
                    job_id=job.job_id,
                    name=job.name,
                    ran_at=current,
                    status="failed",
                    error=str(exc),
                )
            job.last_run_at = current
            job.run_count += 1
            self.history.append(rec)
            ran.append(rec)
        return ran

