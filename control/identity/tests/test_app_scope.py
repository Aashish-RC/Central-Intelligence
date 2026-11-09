"""Tests for App-Level Identity Scoping, Rate Limiting & Isolation (Task 12.6)."""

import pytest
from control.identity.app.app_scope import AppScopeManager


def test_app_data_isolation_and_rate_limiting_acceptance():
    """Acceptance Test: App A can only access its own data; rate limited per app."""
    mgr = AppScopeManager()

    # Register App A and App B
    key_a, app_a = mgr.register_app(
        app_id="app-customer-support",
        name="Customer Support Web UI",
        rate_limit_rpm=2,
        capabilities={"chat:complete", "kb:read"},
    )
    key_b, app_b = mgr.register_app(
        app_id="app-finance-analytics",
        name="Finance Analytics CLI",
        rate_limit_rpm=10,
        capabilities={"analytics:query"},
    )

    # 1. Verify app data isolation
    assert mgr.check_data_isolation(requester_app_id="app-customer-support", target_app_id="app-customer-support") is True
    assert mgr.check_data_isolation(requester_app_id="app-customer-support", target_app_id="app-finance-analytics") is False

    # 2. Authenticate app by key
    auth_a = mgr.authenticate_app_key(key_a)
    assert auth_a.app_id == "app-customer-support"

    # 3. Verify capability scoping
    assert mgr.check_app_capability("app-customer-support", "kb:read") is True
    assert mgr.check_app_capability("app-customer-support", "analytics:query") is False

    # 4. Verify per-app rate limit (App A configured with 2 RPM)
    assert mgr.check_rate_limit("app-customer-support") is True
    assert mgr.check_rate_limit("app-customer-support") is True
    assert mgr.check_rate_limit("app-customer-support") is False

    # Meanwhile App B is unaffected by App A's throttling
    assert mgr.check_rate_limit("app-finance-analytics") is True

