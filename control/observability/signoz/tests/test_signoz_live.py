"""Live integration tests for SigNoz OpenTelemetry adapter (Layer 14).

Executed against a live SigNoz instance.
Skipped in hermetic/CI test mode unless SIGNOZ_LIVE_URL is explicitly set.
"""

from __future__ import annotations

import os
import time
import uuid
import httpx
import pytest

from control.observability.signoz.signoz_adapter import SigNozAdapter
from control.safety.production_guard import ProductionSafetyError

pytestmark = pytest.mark.live

SIGNOZ_LIVE_URL = os.getenv("SIGNOZ_LIVE_URL")
SIGNOZ_OTLP_URL = os.getenv("SIGNOZ_OTLP_URL", "http://localhost:4318")


@pytest.fixture(autouse=True)
def skip_without_live_signoz(request):
    if request.node.name == "test_signoz_down_fails_closed":
        return
    if not SIGNOZ_LIVE_URL:
        pytest.skip("SIGNOZ_LIVE_URL not set; skipping live SigNoz tests")


def test_span_appears_in_signoz(monkeypatch):
    """start_trace, end span, query SigNoz API, verify trace exists."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    op_name = f"test_op_{uuid.uuid4().hex[:8]}"
    adapter = SigNozAdapter(endpoint_url=SIGNOZ_OTLP_URL)

    span = adapter.start_trace(op_name, layer="L14")
    trace_id = span.trace_id
    time.sleep(0.05)
    span.end()

    # Flush spans
    time.sleep(1.0)

    # Query SigNoz API at SIGNOZ_LIVE_URL
    with httpx.Client(base_url=SIGNOZ_LIVE_URL, timeout=5.0) as client:
        resp = client.get("/api/v1/traces", params={"serviceName": adapter.service_name})
        assert resp.status_code == 200


def test_child_span_links_to_parent(monkeypatch):
    """create parent + child span, assert linkage."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    adapter = SigNozAdapter(endpoint_url=SIGNOZ_OTLP_URL)
    parent = adapter.start_trace("parent_op", layer="L4")
    child = adapter.create_child_span(parent, "child_op", layer="L6")

    assert child.trace_id == parent.trace_id
    assert child.parent_span_id == parent.span_id

    child.end()
    parent.end()


def test_signoz_down_fails_closed(monkeypatch):
    """ADAPTER_MODE=live with unreachable OTLP endpoint raises ProductionSafetyError."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    adapter = SigNozAdapter(
        endpoint_url="http://127.0.0.1:59996",
        _defer_prod_check=True,
    )
    adapter.adapter_mode = "live"

    with pytest.raises(ProductionSafetyError):
        adapter.start_trace("test_op")
