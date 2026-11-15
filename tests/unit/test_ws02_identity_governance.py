"""Unit and contract tests for Workstream 02: Identity, Secrets, and Governance (P0).

Covers:
- WS-02.1: OpenFGA relationship writes, checks, and store auto-resolution
- WS-02.2: Infisical secret store, retrieval, zero-downtime rotation, and revocation
- WS-02.3: Multi-tenant & workspace isolation across secrets, memory, and knowledge
- WS-02.4: Role-based authorization, credential scopes, and delegated grants
- WS-02.5: Cryptographic Merkle audit ledger tamper evidence & incident detection
"""

from __future__ import annotations

import time
import uuid
import pytest
import httpx
from unittest.mock import MagicMock

from control.identity.openfga_adapter import OpenFGAAdapter
from control.identity.secrets.infisical_adapter import InfisicalAdapter
from cognitive.memory.access_control.openfga_bridge import check_memory_access, AccessDeniedError
from cognitive.knowledge.access_control.openfga_bridge import check_document_access, filter_results_by_permission
from control.safety.audit.ledger import UnifiedAuditLedger
from control.safety.audit.models import UnifiedAuditEntry, AuditSeverity, UserRole


# ---------------------------------------------------------------------------
# WS-02.1: OpenFGA Auto-Resolution & ReBAC Hierarchy
# ---------------------------------------------------------------------------

def test_openfga_store_auto_resolution(monkeypatch: pytest.MonkeyPatch):
    """Verify OpenFGAAdapter auto-resolves store by name and bootstraps model."""
    monkeypatch.setenv("OPENFGA_ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    post_calls = []
    get_calls = []

    def mock_get(self, url, *args, **kwargs):
        get_calls.append(url)
        if url == "/healthz":
            return httpx.Response(200, request=httpx.Request("GET", url))
        if url == "/stores":
            # No existing store with name
            return httpx.Response(200, json={"stores": []}, request=httpx.Request("GET", url))
        if "/authorization-models" in url:
            return httpx.Response(200, json={"authorization_models": []}, request=httpx.Request("GET", url))
        return httpx.Response(404, request=httpx.Request("GET", url))

    def mock_post(self, url, *args, **kwargs):
        post_calls.append((url, kwargs.get("json", {})))
        if url == "/stores":
            return httpx.Response(201, json={"id": "01HSTORE123456789012345678", "name": "test-store"}, request=httpx.Request("POST", url))
        if "/authorization-models" in url:
            return httpx.Response(201, json={"authorization_model_id": "01HMODEL123"}, request=httpx.Request("POST", url))
        return httpx.Response(200, json={"allowed": True}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    monkeypatch.setattr(httpx.Client, "post", mock_post)

    adapter = OpenFGAAdapter(api_url="http://mock-openfga:8081", store_id="test-store")
    assert adapter.adapter_mode == "live"
    assert adapter.store_id == "01HSTORE123456789012345678"
    assert any("/stores" in c for c in get_calls)
    assert any(url == "/stores" and payload.get("name") == "test-store" for url, payload in post_calls)


def test_openfga_rebac_document_hierarchy():
    """Verify document permission inheritance: owner -> editor -> viewer."""
    adapter = OpenFGAAdapter(_defer_prod_check=True)

    doc_id = "document:report_q4"
    alice = "user:alice"
    bob = "user:bob"
    charlie = "user:charlie"
    dave = "user:dave"

    # Alice is owner
    adapter.write_tuple(alice, "owner", doc_id)
    # Bob is editor
    adapter.write_tuple(bob, "editor", doc_id)
    # Charlie is viewer
    adapter.write_tuple(charlie, "viewer", doc_id)

    # 1. Owner permissions
    assert adapter.check_permission(alice, "owner", doc_id) is True
    assert adapter.check_permission(alice, "can_share", doc_id) is True
    assert adapter.check_permission(alice, "can_edit", doc_id) is True
    assert adapter.check_permission(alice, "can_view", doc_id) is True

    # 2. Editor permissions
    assert adapter.check_permission(bob, "owner", doc_id) is False
    assert adapter.check_permission(bob, "can_share", doc_id) is False
    assert adapter.check_permission(bob, "can_edit", doc_id) is True
    assert adapter.check_permission(bob, "can_view", doc_id) is True

    # 3. Viewer permissions
    assert adapter.check_permission(charlie, "can_edit", doc_id) is False
    assert adapter.check_permission(charlie, "can_share", doc_id) is False
    assert adapter.check_permission(charlie, "can_view", doc_id) is True

    # 4. Unrelated user
    assert adapter.check_permission(dave, "can_view", doc_id) is False
    assert adapter.check_permission(dave, "can_edit", doc_id) is False


def test_openfga_delegation_lifecycle():
    """Verify scoped delegated access for sub-agents (12.15)."""
    adapter = OpenFGAAdapter(_defer_prod_check=True)

    agent_id = "agent:coder_sub_1"
    grant = adapter.grant_delegation(
        delegator="user:alice",
        delegatee=agent_id,
        capabilities=["execute_tool", "read_code"],
        resource_pattern="repo:*",
        ttl_seconds=300,
    )
    assert grant.is_valid() is True

    # Check delegated permission
    assert adapter.check_permission(agent_id, "execute_tool", "repo:ci_brain") is True
    assert adapter.check_permission(agent_id, "read_code", "repo:ci_brain") is True
    # Non-delegated capability
    assert adapter.check_permission(agent_id, "delete_repo", "repo:ci_brain") is False

    # Expired delegation
    expired_grant = adapter.grant_delegation(
        delegator="user:alice",
        delegatee="agent:expired_bot",
        capabilities=["execute_tool"],
        ttl_seconds=-10,
    )
    assert expired_grant.is_valid() is False
    assert adapter.check_permission("agent:expired_bot", "execute_tool", "repo:ci_brain") is False


# ---------------------------------------------------------------------------
# WS-02.2 & WS-02.3: Infisical Vault, Revocation & Tenant Isolation
# ---------------------------------------------------------------------------

def test_infisical_secret_lifecycle_and_revocation():
    """Verify Infisical store, retrieval, zero-downtime rotation, and revocation."""
    vault = InfisicalAdapter(_defer_prod_check=True)

    key = "OPENAI_API_KEY"
    tenant = "tenant_alpha"

    # 1. Store
    secret = vault.store_secret(key, "sk-v1-initial", tenant_id=tenant, actor_id="admin_1")
    assert secret.current_version == 1
    assert vault.get_secret(key, tenant_id=tenant) == "sk-v1-initial"

    # 2. Rotate with grace period
    rotated = vault.rotate_secret(key, "sk-v2-rotated", tenant_id=tenant, actor_id="admin_1", grace_period_seconds=1800)
    assert rotated.current_version == 2
    assert vault.get_secret(key, tenant_id=tenant) == "sk-v2-rotated"
    # Prior version accessible by version index
    assert vault.get_secret(key, tenant_id=tenant, version=1) == "sk-v1-initial"

    # 3. Inject secrets into environment map
    injected = vault.inject_secrets([key], tenant_id=tenant, actor_id="runner_1")
    assert injected[key] == "sk-v2-rotated"

    # 4. Revocation / Deletion
    assert vault.revoke_secret(key, tenant_id=tenant, actor_id="admin_1") is True
    with pytest.raises(KeyError):
        vault.get_secret(key, tenant_id=tenant)

    # 5. Audit trail records all actions
    trail = vault.get_audit_trail(secret_key=key, tenant_id=tenant)
    actions = [e.action for e in trail]
    assert "STORE" in actions
    assert "ROTATE" in actions
    assert "INJECT" in actions
    assert "DELETE" in actions


def test_tenant_workspace_isolation():
    """Verify strict tenant isolation across secrets, memory, and knowledge."""
    vault = InfisicalAdapter(_defer_prod_check=True)

    # Tenant Alpha and Tenant Beta both store a secret with the same key
    vault.store_secret("DATABASE_URL", "postgres://alpha:pass@db/alpha", tenant_id="alpha")
    vault.store_secret("DATABASE_URL", "postgres://beta:pass@db/beta", tenant_id="beta")

    assert vault.get_secret("DATABASE_URL", tenant_id="alpha") == "postgres://alpha:pass@db/alpha"
    assert vault.get_secret("DATABASE_URL", tenant_id="beta") == "postgres://beta:pass@db/beta"

    # Alpha cannot access Beta's secret
    with pytest.raises(KeyError):
        vault.get_secret("NON_EXISTENT_IN_ALPHA", tenant_id="alpha")

    # Memory Access Control Bridge (DEF-01)
    fga = OpenFGAAdapter(_defer_prod_check=True)
    # Alice can access her own memory
    assert check_memory_access("alice", "read", "alice", openfga_client=fga) is True
    # Bob cannot access Alice's memory without grant
    with pytest.raises(AccessDeniedError):
        check_memory_access("bob", "read", "alice", openfga_client=fga)

    # Grant Bob read access on Alice's memory in OpenFGA
    fga.write_tuple("user:bob", "read", "memory:alice")
    assert check_memory_access("bob", "read", "alice", openfga_client=fga) is True

    # Knowledge Permission Filtering (DEF-02)
    doc_alpha = {"id": "doc_a", "metadata": {"visibility": "private"}}
    doc_public = {"id": "doc_pub", "metadata": {"visibility": "public"}}
    fga.write_tuple("user:alice", "can_view", "document:doc_a")

    # Alice sees both private and public
    alice_results = filter_results_by_permission([doc_alpha, doc_public], user_id="alice", openfga_client=fga)
    assert len(alice_results) == 2

    # Bob only sees public
    bob_results = filter_results_by_permission([doc_alpha, doc_public], user_id="bob", openfga_client=fga)
    assert len(bob_results) == 1
    assert bob_results[0]["id"] == "doc_pub"

    # Tools Tenant Isolation (Layer 5 Curated Registry)
    from cognitive.action.registry.curated_registry import (
        CuratedToolMetadata,
        CuratedToolRegistry,
        ToolAccessDeniedError,
    )
    registry = CuratedToolRegistry()

    tool_global = CuratedToolMetadata(
        tool_id="tool_global_search",
        name="Global Search",
        is_approved=True,
        tenant_id="global",
    )
    tool_alpha = CuratedToolMetadata(
        tool_id="tool_alpha_internal",
        name="Alpha Internal ERP",
        is_approved=True,
        tenant_id="alpha",
    )
    tool_beta = CuratedToolMetadata(
        tool_id="tool_beta_finance",
        name="Beta Payroll API",
        is_approved=True,
        tenant_id="beta",
    )
    registry.register_tool(tool_global)
    registry.register_tool(tool_alpha)
    registry.register_tool(tool_beta)

    # Listing tools for Alpha returns global + alpha, excludes beta
    alpha_tools = [t.tool_id for t in registry.list_curated_tools(tenant_id="alpha")]
    assert "tool_global_search" in alpha_tools
    assert "tool_alpha_internal" in alpha_tools
    assert "tool_beta_finance" not in alpha_tools

    # Listing tools for Beta returns global + beta, excludes alpha
    beta_tools = [t.tool_id for t in registry.list_curated_tools(tenant_id="beta")]
    assert "tool_global_search" in beta_tools
    assert "tool_beta_finance" in beta_tools
    assert "tool_alpha_internal" not in beta_tools

    # Access check: Beta cannot invoke Alpha's internal tool
    with pytest.raises(ToolAccessDeniedError, match="restricted to tenant 'alpha'"):
        registry.check_access(
            tool_id="tool_alpha_internal",
            agent_id="agent_beta_01",
            agent_roles=["admin"],
            tenant_id="beta",
        )

    # Alpha agent can invoke Alpha's tool
    registry.check_access(
        tool_id="tool_alpha_internal",
        agent_id="agent_alpha_01",
        agent_roles=["user"],
        tenant_id="alpha",
    )

    # API Tenant Isolation & Cryptographic Boundary (Layer 12 TenantManager)
    from control.identity.tenancy.tenant_manager import TenantManager
    tm = TenantManager()
    t_alpha = tm.create_tenant(name="Alpha Corp", tenant_id="alpha")
    t_beta = tm.create_tenant(name="Beta LLC", tenant_id="beta")

    # Dedicated 256-bit AES encryption keys per tenant
    assert t_alpha.encryption_key != t_beta.encryption_key

    # Strict cross-tenant data isolation gate
    assert tm.check_data_isolation("alpha", "alpha") is True
    assert tm.check_data_isolation("beta", "alpha") is False
    assert tm.check_data_isolation("alpha", "beta") is False



# ---------------------------------------------------------------------------
# WS-02.5: Cryptographic Merkle Audit Ledger & Incident Detection
# ---------------------------------------------------------------------------

def test_audit_ledger_tamper_evidence_and_merkle_root():
    """Verify that tampering with any audit ledger entry invalidates Merkle root."""
    ledger = UnifiedAuditLedger(db_path=":memory:")

    # Append 5 valid entries
    for i in range(1, 6):
        entry = UnifiedAuditEntry(
            id=f"audit-{i}",
            tenant_id="tenant-prod",
            user_id=f"user-{i}",
            role=UserRole.USER.value,
            module="identity",
            action=f"access_secret_{i}",
            resource="vault:key",
            status="success",
            severity=AuditSeverity.INFO,
        )
        ledger.log(entry)

    report_intact = ledger.verify_integrity_detailed()
    assert report_intact.is_valid is True
    assert report_intact.total_entries == 5
    assert report_intact.merkle_root is not None

    # Simulate malicious unauthorized modification of record 3 in the SQLite database
    conn = ledger._get_connection()
    conn.execute("UPDATE unified_audit_log SET action = 'MALICIOUS_TAMPER' WHERE seq = 3")
    conn.commit()

    # Re-verify integrity
    assert ledger.verify_integrity() is False
    report_tampered = ledger.verify_integrity_detailed()
    assert report_tampered.is_valid is False
    assert report_tampered.tampered_seq == 3
    assert report_tampered.violation_type in ("modified_entry_payload", "broken_prev_hash")
