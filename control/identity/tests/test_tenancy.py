"""Tests for Multi-Tenant Isolation & Lifecycle Management (Task 12.5)."""

import pytest
from control.identity.tenancy.tenant_manager import TenantManager, TenantStatus


def test_tenant_isolation_and_encryption_keys_acceptance():
    """Acceptance Test: Tenant A's data is invisible to Tenant B; each tenant has its own encryption key."""
    mgr = TenantManager()

    # Create Tenant A and Tenant B
    tenant_a = mgr.create_tenant(name="Acme Corporation", tenant_id="tnt-acme")
    tenant_b = mgr.create_tenant(name="Beta Industries", tenant_id="tnt-beta")

    # 1. Verify dedicated encryption keys
    key_a = mgr.get_tenant_encryption_key("tnt-acme")
    key_b = mgr.get_tenant_encryption_key("tnt-beta")

    assert len(key_a) == 64  # 32 bytes hex = 256 bits
    assert len(key_b) == 64
    assert key_a != key_b

    # 2. Verify data isolation boundary
    assert mgr.check_data_isolation(requester_tenant_id="tnt-acme", resource_owner_tenant_id="tnt-acme") is True
    assert mgr.check_data_isolation(requester_tenant_id="tnt-acme", resource_owner_tenant_id="tnt-beta") is False


def test_tenant_rate_limiting():
    """Validates per-tenant sliding-window RPM rate limits."""
    mgr = TenantManager()
    tenant = mgr.create_tenant(name="Startup Limited", tenant_id="tnt-rate-test", rate_limit_rpm=3)

    # 3 requests allowed
    assert mgr.check_rate_limit("tnt-rate-test") is True
    assert mgr.check_rate_limit("tnt-rate-test") is True
    assert mgr.check_rate_limit("tnt-rate-test") is True

    # 4th request blocked by rate limit
    assert mgr.check_rate_limit("tnt-rate-test") is False


def test_tenant_lifecycle_suspension_and_deletion():
    """Validates tenant suspension and deletion states."""
    mgr = TenantManager()
    tenant = mgr.create_tenant(name="Test Lifecycle", tenant_id="tnt-lifecycle")

    # Suspend
    mgr.suspend_tenant("tnt-lifecycle")
    assert mgr.get_tenant("tnt-lifecycle").status == TenantStatus.SUSPENDED

    # Suspended tenant cannot check rate limits or fetch encryption key
    with pytest.raises(PermissionError, match="not active"):
        mgr.get_tenant_encryption_key("tnt-lifecycle")

    # Reactivate
    mgr.activate_tenant("tnt-lifecycle")
    assert mgr.get_tenant("tnt-lifecycle").status == TenantStatus.ACTIVE

    # Delete
    assert mgr.delete_tenant("tnt-lifecycle") is True
    with pytest.raises(KeyError, match="not found or deleted"):
        mgr.get_tenant("tnt-lifecycle")

