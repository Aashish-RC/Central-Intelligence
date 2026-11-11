"""Tests for ReplayableEventStream (L15 Feature 15.29)."""

from __future__ import annotations

import pytest

from platform_infra.data.messaging.replay import ReplayableEventStream


@pytest.mark.asyncio
async def test_replay_from_offset_and_timestamp() -> None:
    stream = ReplayableEventStream()
    stream.append("audit", {"seq": 1}, timestamp=100.0)
    stream.append("audit", {"seq": 2}, timestamp=200.0)
    stream.append("audit", {"seq": 3}, timestamp=300.0)

    assert [r.payload["seq"] for r in stream.replay_from_offset("audit", 1)] == [2, 3]
    assert [r.payload["seq"] for r in stream.replay_from_timestamp("audit", 200.0)] == [2, 3]

    seen = []
    count = await stream.replay_into("audit", lambda r: seen.append(r.payload["seq"]), since_ts=150.0)
    assert count == 2
    assert seen == [2, 3]

