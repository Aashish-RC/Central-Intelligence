"""Tests for EventBus (L15 Features 15.27, 15.28)."""

from __future__ import annotations

import pytest

from control.safety.production_guard import ProductionSafetyError
from platform_infra.data.messaging.event_bus import EventBus


@pytest.mark.asyncio
async def test_event_bus_priority_order_and_dlq() -> None:
    bus = EventBus()
    received = []

    await bus.publish("tasks", {"msg": "low"}, priority=1)
    await bus.publish("tasks", {"msg": "high"}, priority=10)
    await bus.publish("tasks", {"msg": "fail", "bad": True}, priority=5)

    def handler(evt):
        if evt.get("bad"):
            raise ValueError("boom")
        received.append(evt["msg"])

    await bus.subscribe("tasks", handler)
    assert received == ["high", "low"]
    dlq = bus.inspect_dlq("tasks")
    assert len(dlq) == 1
    assert dlq[0]["event"]["msg"] == "fail"
    assert "boom" in dlq[0]["reason"]


def test_event_bus_fails_closed_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ProductionSafetyError):
        EventBus()

