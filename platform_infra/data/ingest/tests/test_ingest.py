"""Tests for StreamingIngestPipeline & BatchIngestScheduler (L15 Features 15.32, 15.33)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from platform_infra.data.ingest.batch_ingest import BatchIngestScheduler, cron_matches
from platform_infra.data.ingest.stream_ingest import StreamingIngestPipeline


@pytest.mark.asyncio
async def test_streaming_ingest_throughput_above_1000_eps() -> None:
    pipeline = StreamingIngestPipeline(
        transform=lambda e: {"id": e["i"], "v": e["i"] * 2},
        batch_size=500,
    )
    events = [{"i": i} for i in range(2500)]
    stats = await pipeline.ingest_iterable(events)
    assert stats.stored == 2500
    assert stats.failed == 0
    assert stats.events_per_second >= 1000.0
    assert pipeline.stored_records[0] == {"id": 0, "v": 0}


@pytest.mark.asyncio
async def test_batch_ingest_cron_scheduling() -> None:
    scheduler = BatchIngestScheduler()
    ran_items = []
    scheduler.schedule("daily-sync", "0 2 * * *", lambda: ran_items.append("ok") or 42)

    dt_miss = datetime(2026, 11, 11, 3, 0, tzinfo=timezone.utc)
    dt_hit = datetime(2026, 11, 11, 2, 0, tzinfo=timezone.utc)
    assert cron_matches("0 2 * * *", dt_hit)
    assert await scheduler.tick(dt_miss) == []

    runs = await scheduler.tick(dt_hit)
    assert len(runs) == 1
    assert runs[0].status == "succeeded"
    assert runs[0].items_processed == 42

