"""Tests for Tenant-Level Sandbox and Simulation Test Mode (Task 11.11, Feature 11.25)."""

import pytest
from control.evaluation.sandbox.tenant_sandbox import TenantSandboxManager


def test_tenant_sandbox_simulation_acceptance():
    """Acceptance Test: In sandbox mode, agent's 'send email' action is simulated, not executed."""
    sandbox = TenantSandboxManager()
    tenant_id = "tenant-fin-corp"

    # Enable sandbox for tenant
    sandbox.enable_sandbox(tenant_id)
    assert sandbox.is_sandbox_active(tenant_id) is True

    # Mutating tool 'send_email' must be intercepted and simulated
    params = {"to": "ceo@enterprise.com", "subject": "Quarterly Report", "body": "See attached."}
    is_sim, output = sandbox.intercept(tool_name="send_email", parameters=params, tenant_id=tenant_id)

    assert is_sim is True
    assert output is not None
    assert output["is_simulation"] is True
    assert output["status"] == "simulated_success"
    assert "send_email" in output["message"]
    assert "[SANDBOX MODE]" in output["message"]

    # Check audit log
    records = sandbox.get_simulated_actions(tenant_id=tenant_id)
    assert len(records) == 1
    assert records[0].tool_name == "send_email"
    assert records[0].parameters == params


def test_tenant_sandbox_whitelisted_and_disabled():
    """Verifies that whitelisted read tools execute and disabled sandbox bypasses simulation."""
    sandbox = TenantSandboxManager()
    tenant_id = "tenant-002"

    sandbox.enable_sandbox(tenant_id, whitelist_live_tools={"search_knowledge", "read_file"})

    # Whitelisted read tool is NOT simulated
    is_sim, output = sandbox.intercept("search_knowledge", {"query": "AI docs"}, tenant_id=tenant_id)
    assert is_sim is False
    assert output is None

    # Disable sandbox
    sandbox.disable_sandbox(tenant_id)
    assert sandbox.is_sandbox_active(tenant_id) is False

    # Now even 'send_email' is not intercepted by sandbox
    is_sim2, output2 = sandbox.intercept("send_email", {"to": "user@test.com"}, tenant_id=tenant_id)
    assert is_sim2 is False
    assert output2 is None
