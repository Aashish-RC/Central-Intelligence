"""Tests for Infisical Secret Vault & Lifecycle Adapter (Task 12.3)."""

import pytest
from control.identity.secrets.infisical_adapter import InfisicalAdapter


def test_infisical_store_retrieve_rotate_audit_acceptance():
    """Acceptance Test: Can store an OpenAI API key, retrieve it, rotate it, audit who accessed it."""
    vault = InfisicalAdapter()
    tenant = "tenant-enterprise-1"
    app = "reasoning-agent-v1"

    # 1. Store OpenAI API key (v1)
    secret_rec = vault.store_secret(
        key="OPENAI_API_KEY",
        value="sk-proj-original-key-1111",
        tenant_id=tenant,
        app_id=app,
        actor_id="admin_user",
        metadata={"provider": "openai", "model_tier": "tier-3"},
    )
    assert secret_rec.current_version == 1
    assert secret_rec.current_value == "sk-proj-original-key-1111"

    # 2. Retrieve secret as an executing agent runner
    val1 = vault.get_secret(
        key="OPENAI_API_KEY",
        tenant_id=tenant,
        app_id=app,
        actor_id="agent_runner_pod_42",
    )
    assert val1 == "sk-proj-original-key-1111"

    # 3. Rotate secret without downtime (v2)
    rotated_rec = vault.rotate_secret(
        key="OPENAI_API_KEY",
        new_value="sk-proj-rotated-key-2222",
        tenant_id=tenant,
        app_id=app,
        actor_id="security_bot",
        grace_period_seconds=1800,
    )
    assert rotated_rec.current_version == 2
    assert rotated_rec.current_value == "sk-proj-rotated-key-2222"

    # Verify new reads return v2
    val2 = vault.get_secret("OPENAI_API_KEY", tenant_id=tenant, app_id=app, actor_id="agent_runner_pod_42")
    assert val2 == "sk-proj-rotated-key-2222"

    # Verify old v1 still accessible by explicit version during zero-downtime grace period
    val_v1 = vault.get_secret("OPENAI_API_KEY", tenant_id=tenant, app_id=app, actor_id="agent_legacy", version=1)
    assert val_v1 == "sk-proj-original-key-1111"

    # 4. Audit who accessed the secret
    audit_trail = vault.get_audit_trail(secret_key="OPENAI_API_KEY", tenant_id=tenant)
    assert len(audit_trail) >= 4

    actions = [e.action for e in audit_trail]
    actors = [e.actor_id for e in audit_trail]

    assert "STORE" in actions
    assert "READ" in actions
    assert "ROTATE" in actions
    assert "admin_user" in actors
    assert "agent_runner_pod_42" in actors
    assert "security_bot" in actors


def test_infisical_tenant_and_app_scoping():
    """Validates strict scoping preventing cross-tenant and cross-app secret leakage."""
    vault = InfisicalAdapter()

    vault.store_secret(key="DB_PASS", value="secretA", tenant_id="tenantA", app_id="app1")
    vault.store_secret(key="DB_PASS", value="secretB", tenant_id="tenantB", app_id="app1")

    assert vault.get_secret("DB_PASS", tenant_id="tenantA", app_id="app1") == "secretA"
    assert vault.get_secret("DB_PASS", tenant_id="tenantB", app_id="app1") == "secretB"

    # Nonexistent tenant/app raises KeyError
    with pytest.raises(KeyError):
        vault.get_secret("DB_PASS", tenant_id="tenantC", app_id="app1")


def test_infisical_env_injection():
    """Validates batch injection into runtime environment."""
    vault = InfisicalAdapter()
    vault.store_secret("ANTHROPIC_API_KEY", "sk-ant-test", tenant_id="t1")
    vault.store_secret("GEMINI_API_KEY", "gm-test-123", tenant_id="t1")

    injected = vault.inject_secrets(["ANTHROPIC_API_KEY", "GEMINI_API_KEY", "MISSING_KEY"], tenant_id="t1")
    assert injected["ANTHROPIC_API_KEY"] == "sk-ant-test"
    assert injected["GEMINI_API_KEY"] == "gm-test-123"
    assert "MISSING_KEY" not in injected

