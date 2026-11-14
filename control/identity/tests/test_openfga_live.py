"""Live integration tests for OpenFGA ReBAC adapter (Layer 12).

Executed against a live OpenFGA service.
Skipped in hermetic/CI test mode unless OPENFGA_LIVE_URL is explicitly set.
"""

from __future__ import annotations

import os
import uuid
import httpx
import pytest

from control.identity.openfga_adapter import OpenFGAAdapter
from control.safety.production_guard import ProductionSafetyError

pytestmark = pytest.mark.live

OPENFGA_LIVE_URL = os.getenv("OPENFGA_LIVE_URL")


@pytest.fixture(scope="module")
def live_openfga_store():
    """Ensure a store with a valid document/user schema exists on the live OpenFGA instance."""
    if not OPENFGA_LIVE_URL:
        pytest.skip("OPENFGA_LIVE_URL not set; skipping live OpenFGA tests")

    store_name = f"test-store-{uuid.uuid4().hex[:8]}"
    client = httpx.Client(base_url=OPENFGA_LIVE_URL, timeout=5.0)

    # 1. Create store
    create_resp = client.post("/stores", json={"name": store_name})
    assert create_resp.status_code in (200, 201), f"Failed to create store: {create_resp.text}"
    store_id = create_resp.json()["id"]

    # 2. Write authorization model
    model_payload = {
        "schema_version": "1.1",
        "type_definitions": [
            {
                "type": "user",
                "relations": {},
            },
            {
                "type": "document",
                "relations": {
                    "viewer": {"this": {}},
                    "editor": {"this": {}},
                    "owner": {"this": {}},
                },
                "metadata": {
                    "relations": {
                        "viewer": {"directly_related_user_types": [{"type": "user"}]},
                        "editor": {"directly_related_user_types": [{"type": "user"}]},
                        "owner": {"directly_related_user_types": [{"type": "user"}]},
                    }
                },
            },
        ],
    }
    model_resp = client.post(f"/stores/{store_id}/authorization-models", json=model_payload)
    assert model_resp.status_code in (200, 201), f"Failed to write model: {model_resp.text}"

    yield store_id


def test_tuple_persists_across_restart(live_openfga_store, monkeypatch):
    """Write a tuple via OpenFGAAdapter, instantiate a NEW adapter, assert check_permission returns True."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    doc_id = f"document:{uuid.uuid4().hex[:8]}"
    user_id = f"user:{uuid.uuid4().hex[:8]}"

    # Adapter instance 1
    adapter_1 = OpenFGAAdapter(api_url=OPENFGA_LIVE_URL, store_id=live_openfga_store)
    adapter_1.write_tuple(user_id, "viewer", doc_id)

    # Adapter instance 2 (new memory state, same live store)
    adapter_2 = OpenFGAAdapter(api_url=OPENFGA_LIVE_URL, store_id=live_openfga_store)
    assert (user_id, "viewer", doc_id) not in adapter_2._tuples  # Verify not in local memory

    has_perm = adapter_2.check_permission(user_id, "viewer", doc_id)
    assert has_perm is True, "Permission check failed on fresh adapter instance against live OpenFGA"


def test_live_check_returns_false_for_unrelated_user(live_openfga_store, monkeypatch):
    """Writing user:alice as viewer on document:1 must return False for user:bob."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    doc_id = f"document:{uuid.uuid4().hex[:8]}"
    alice = "user:alice"
    bob = "user:bob"

    adapter = OpenFGAAdapter(api_url=OPENFGA_LIVE_URL, store_id=live_openfga_store)
    adapter.write_tuple(alice, "viewer", doc_id)

    # Alice is allowed
    assert adapter.check_permission(alice, "viewer", doc_id) is True
    # Bob is not allowed
    assert adapter.check_permission(bob, "viewer", doc_id) is False


def test_openfga_down_fails_closed(monkeypatch):
    """When ADAPTER_MODE=live and OpenFGA is unreachable, init and write_tuple raise ProductionSafetyError."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    # Point to invalid port - init fails closed
    with pytest.raises(ProductionSafetyError):
        OpenFGAAdapter(
            api_url="http://127.0.0.1:59999",
            store_id="dummy-store",
        )

    # Even if prod check was deferred, write_tuple fails closed in live mode
    adapter = OpenFGAAdapter(
        api_url="http://127.0.0.1:59999",
        store_id="dummy-store",
        _defer_prod_check=True,
    )
    adapter.adapter_mode = "live"
    with pytest.raises(ProductionSafetyError):
        adapter.write_tuple("user:alice", "viewer", "document:1")
