"""Unit tests for AppSandbox (Task 15.5)."""

import pytest
import time
from platform.data.isolation.app_sandbox import (
    AppSandbox,
    PermissionDeniedError,
    SandboxConfig,
)


@pytest.fixture
def sandbox():
    return AppSandbox(config=SandboxConfig(strict_mode=True, audit_enabled=True))


def test_app_own_data_access(sandbox: AppSandbox):
    """Test app can freely read and write within its own isolated sandbox."""
    doc = {"title": "Q3 Financials", "confidential": True}
    sandbox.insert("app_finance", "documents", "doc_101", doc)

    fetched = sandbox.get("app_finance", "documents", "doc_101")
    assert fetched == doc


def test_cross_app_access_denied_without_grant(sandbox: AppSandbox):
    """App A's data is isolated; App B cannot read without explicit grant."""
    sandbox.insert("app_crm", "contacts", "c_1", {"name": "Bob", "email": "bob@example.com"})

    # App Analytics tries to read CRM contacts
    with pytest.raises(PermissionDeniedError, match="Access denied: App 'app_analytics' cannot read"):
        sandbox.get("app_crm", "contacts", "c_1", requester_app_id="app_analytics")

    # App Analytics tries to query CRM contacts
    with pytest.raises(PermissionDeniedError):
        sandbox.query("app_crm", "contacts", requester_app_id="app_analytics")


def test_cross_app_access_allowed_with_grant_and_revocation(sandbox: AppSandbox):
    """App A grants App B read access, then revokes it."""
    sandbox.insert("app_crm", "contacts", "c_2", {"name": "Charlie", "lead_score": 90})

    # Grant read access
    sandbox.grant_cross_app_access(
        grantor_app_id="app_crm",
        grantee_app_id="app_analytics",
        collection="contacts",
        permissions={"read"},
    )

    # Now App Analytics can read
    fetched = sandbox.get("app_crm", "contacts", "c_2", requester_app_id="app_analytics")
    assert fetched is not None
    assert fetched["name"] == "Charlie"

    # But App Analytics cannot write
    with pytest.raises(PermissionDeniedError, match="cannot write"):
        sandbox.insert(
            "app_crm",
            "contacts",
            "c_malicious",
            {"hacked": True},
            requester_app_id="app_analytics",
        )

    # Revoke access
    sandbox.revoke_cross_app_access("app_crm", "app_analytics", "contacts")
    with pytest.raises(PermissionDeniedError):
        sandbox.get("app_crm", "contacts", "c_2", requester_app_id="app_analytics")


def test_expired_access_grant(sandbox: AppSandbox):
    """Grant with expired TTL is rejected."""
    sandbox.insert("app_hr", "salaries", "s_1", {"amount": 120000})

    grant = sandbox.grant_cross_app_access(
        grantor_app_id="app_hr",
        grantee_app_id="app_auditor",
        collection="salaries",
        ttl_seconds=1.0,
    )
    # Manually expire
    grant.expires_at = time.time() - 10

    with pytest.raises(PermissionDeniedError):
        sandbox.get("app_hr", "salaries", "s_1", requester_app_id="app_auditor")

