"""Live integration tests for Infisical KMS Vault adapter (Layer 12).

Executed against a live Infisical KMS service.
Skipped in hermetic/CI test mode unless INFISICAL_LIVE_URL is explicitly set.
"""

from __future__ import annotations

import os
import uuid
import pytest

from control.identity.secrets.infisical_adapter import InfisicalAdapter
from control.safety.production_guard import ProductionSafetyError

pytestmark = pytest.mark.live

INFISICAL_LIVE_URL = os.getenv("INFISICAL_LIVE_URL")
INFISICAL_CLIENT_ID = os.getenv("INFISICAL_CLIENT_ID")
INFISICAL_CLIENT_SECRET = os.getenv("INFISICAL_CLIENT_SECRET")


@pytest.fixture(autouse=True)
def skip_without_live_infisical(request):
    if request.node.name == "test_unauthorized_in_live_mode_fails_closed":
        return
    if not INFISICAL_LIVE_URL:
        pytest.skip("INFISICAL_LIVE_URL not set; skipping live Infisical tests")


def test_secret_persists_across_restart(monkeypatch):
    """Store secret via adapter 1, instantiate fresh adapter 2, verify get_secret succeeds."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    key = f"TEST_SECRET_{uuid.uuid4().hex[:8]}"
    val = f"secret-val-{uuid.uuid4().hex}"

    adapter_1 = InfisicalAdapter(
        server_url=INFISICAL_LIVE_URL,
        client_id=INFISICAL_CLIENT_ID,
        client_secret=INFISICAL_CLIENT_SECRET,
    )
    adapter_1.store_secret(key, val)

    # Fresh adapter instance without in-memory state
    adapter_2 = InfisicalAdapter(
        server_url=INFISICAL_LIVE_URL,
        client_id=INFISICAL_CLIENT_ID,
        client_secret=INFISICAL_CLIENT_SECRET,
    )
    s_key = adapter_2._scope_key(key, "default", None)
    assert s_key not in adapter_2._vault

    retrieved = adapter_2.get_secret(key)
    assert retrieved == val


def test_missing_secret_raises_keyerror(monkeypatch):
    """Querying a non-existent secret in live mode raises KeyError."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    adapter = InfisicalAdapter(
        server_url=INFISICAL_LIVE_URL,
        client_id=INFISICAL_CLIENT_ID,
        client_secret=INFISICAL_CLIENT_SECRET,
    )
    missing_key = f"NON_EXISTENT_{uuid.uuid4().hex}"
    with pytest.raises(KeyError):
        adapter.get_secret(missing_key)


def test_unauthorized_in_live_mode_fails_closed(monkeypatch):
    """Initializing with invalid host/credentials under ADAPTER_MODE=live raises ProductionSafetyError."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    with pytest.raises(ProductionSafetyError):
        InfisicalAdapter(server_url="http://localhost:9", client_id="bad")
