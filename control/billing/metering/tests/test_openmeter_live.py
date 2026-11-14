"""Live integration tests for OpenMeter metering adapter (Layer 13).

Executed against a live OpenMeter service.
Skipped in hermetic/CI test mode unless OPENMETER_LIVE_URL is explicitly set.
"""

from __future__ import annotations

import os
import time
import uuid
import pytest

from control.billing.metering.openmeter_adapter import OpenMeterAdapter
from control.billing.models import TokenUsageEvent
from control.safety.production_guard import ProductionSafetyError

pytestmark = pytest.mark.live

OPENMETER_LIVE_URL = os.getenv("OPENMETER_LIVE_URL")


@pytest.fixture(autouse=True)
def skip_without_live_openmeter(request):
    if request.node.name == "test_live_query_fails_closed_when_openmeter_down":
        return
    if not OPENMETER_LIVE_URL:
        pytest.skip("OPENMETER_LIVE_URL not set; skipping live OpenMeter tests")


def test_event_appears_in_live_query(monkeypatch):
    """record_event with dispatch_remote=True appears in live query_usage."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    user_id = f"test-user-{uuid.uuid4().hex[:8]}"
    adapter = OpenMeterAdapter(endpoint_url=OPENMETER_LIVE_URL)

    event = TokenUsageEvent(
        user_id=user_id,
        tenant_id="live-tenant",
        app_id="chat",
        model="gpt-4o",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd=0.005,
        billable=True,
    )
    result = adapter.record_event(event, dispatch_remote=True)
    assert result["remote_dispatched"] is True

    # Allow OpenMeter buffer ingestion
    time.sleep(0.3)

    # Empty local events to prove query reads from live backend
    adapter._local_events = []
    summary = adapter.query_usage(user_id=user_id)
    assert summary.total_tokens >= 150


def test_live_query_fails_closed_when_openmeter_down(monkeypatch):
    """ADAPTER_MODE=live with OpenMeter unreachable fails closed with ProductionSafetyError."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    adapter = OpenMeterAdapter(
        endpoint_url="http://127.0.0.1:59998",
        _defer_prod_check=True,
    )
    adapter.adapter_mode = "live"

    with pytest.raises(ProductionSafetyError):
        adapter.query_usage(user_id="alice")
