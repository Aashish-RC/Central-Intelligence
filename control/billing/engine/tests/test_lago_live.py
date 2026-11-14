"""Live integration tests for Lago billing engine adapter (Layer 13).

Executed against a live Lago billing service.
Skipped in hermetic/CI test mode unless LAGO_LIVE_URL is explicitly set.
"""

from __future__ import annotations

import os
import uuid
import pytest

from control.billing.engine.lago_adapter import LagoAdapter
from control.safety.production_guard import ProductionSafetyError

pytestmark = pytest.mark.live

LAGO_LIVE_URL = os.getenv("LAGO_LIVE_URL")
LAGO_API_KEY = os.getenv("LAGO_API_KEY")


@pytest.fixture(autouse=True)
def skip_without_live_lago(request):
    if request.node.name == "test_lago_down_fails_closed":
        return
    if not LAGO_LIVE_URL:
        pytest.skip("LAGO_LIVE_URL not set; skipping live Lago tests")


def test_subscription_persists_in_lago(monkeypatch):
    """subscribe_customer persists to Lago and is recognized by a new LagoAdapter instance."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    customer_id = f"cust_{uuid.uuid4().hex[:8]}"
    adapter_1 = LagoAdapter(api_url=LAGO_LIVE_URL, api_key=LAGO_API_KEY)
    sub = adapter_1.subscribe_customer(customer_id, "free")
    assert sub.subscription_id is not None

    # Instance 2 (new memory state)
    adapter_2 = LagoAdapter(api_url=LAGO_LIVE_URL, api_key=LAGO_API_KEY)
    assert customer_id not in adapter_2._subscriptions

    allowed, msg = adapter_2.check_entitlement(customer_id, requested_tokens=100)
    assert allowed is True
    assert msg == "Authorized"


def test_invoice_generated_in_lago(monkeypatch):
    """generate_invoice issues call to /api/v1/invoices and records invoice in live Lago."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    customer_id = f"cust_{uuid.uuid4().hex[:8]}"
    adapter = LagoAdapter(api_url=LAGO_LIVE_URL, api_key=LAGO_API_KEY)
    adapter.subscribe_customer(customer_id, "free")

    inv = adapter.generate_invoice(customer_id=customer_id)
    assert inv.status == "open"
    assert inv.customer_id == customer_id


def test_lago_down_fails_closed(monkeypatch):
    """ADAPTER_MODE=live with Lago unreachable raises ProductionSafetyError."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    adapter = LagoAdapter(
        api_url="http://127.0.0.1:59997",
        _defer_prod_check=True,
    )
    adapter.adapter_mode = "live"

    with pytest.raises(ProductionSafetyError):
        adapter.subscribe_customer("alice", "free")
