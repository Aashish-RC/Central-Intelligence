"""
Unit and integration tests for Observability Dashboards (14.15, 14.16, 14.17, 14.18).
"""

import time
import pytest
from control.observability.dashboards.executive_dashboard import ExecutiveDashboard
from control.observability.dashboards.per_app_dashboard import PerAppDashboard
from control.observability.dashboards.per_tenant_dashboard import PerTenantDashboard
from control.observability.dashboards.realtime_dashboard import RealtimeDashboard
from control.observability.models import TraceStatus
from control.observability.posthog.posthog_adapter import PostHogAdapter
from control.observability.signoz.signoz_adapter import SigNozAdapter


@pytest.fixture
def populated_signoz():
    """Builds a SigNoz adapter instance with multi-tenant, multi-app telemetry."""
    signoz = SigNozAdapter()
    now = time.time()

    # Tenant 1 (Finance App)
    s1 = signoz.start_trace("eval_run", layer="L11", attributes={"tenant_id": "tenant_alpha", "app_id": "finance_ai", "user_id": "u1"})
    s1.start_time = now - 50
    s1.finish(TraceStatus.OK)
    s1.duration_ms = 120.0
    signoz.record_token_usage("u1", "tenant_alpha", "claude-3-5-sonnet", prompt_tokens=200, completion_tokens=50, cost_usd=0.005)

    s2 = signoz.start_trace("eval_run_err", layer="L11", attributes={"tenant_id": "tenant_alpha", "app_id": "finance_ai", "user_id": "u1"})
    s2.start_time = now - 40
    s2.finish(TraceStatus.ERROR)
    s2.duration_ms = 350.0

    # Tenant 2 (Healthcare App)
    s3 = signoz.start_trace("med_query", layer="L4", attributes={"tenant_id": "tenant_beta", "app_id": "health_bot", "user_id": "u2"})
    s3.start_time = now - 30
    s3.finish(TraceStatus.OK)
    s3.duration_ms = 85.0
    signoz.record_token_usage("u2", "tenant_beta", "gpt-4o", prompt_tokens=400, completion_tokens=100, cost_usd=0.015)

    return signoz


def test_realtime_system_dashboard_admin_and_auth(populated_signoz):
    """
    14.15: Real-time system dashboard.
    Acceptance: Admin sees real-time system dashboard; non-admin is rejected.
    """
    dashboard = RealtimeDashboard(signoz_adapter=populated_signoz)

    # Non-admin access should be denied
    with pytest.raises(PermissionError, match="admin privileges"):
        dashboard.get_system_metrics(requester_role="viewer")

    with pytest.raises(PermissionError, match="admin privileges"):
        dashboard.get_system_metrics(requester_role="tenant_user")

    # Admin access succeeds
    metrics = dashboard.get_system_metrics(requester_role="admin")
    assert metrics.total_requests == 3
    assert metrics.error_count == 1
    assert metrics.error_rate == pytest.approx(1 / 3, rel=1e-2)
    assert metrics.throughput_rps > 0.0
    assert metrics.percentiles.sample_count == 3
    assert metrics.percentiles.p50_ms > 0.0
    assert metrics.total_tokens_processed == 750  # 250 from alpha + 500 from beta
    assert metrics.total_cost_usd == pytest.approx(0.020, rel=1e-3)


def test_per_tenant_dashboard_isolation(populated_signoz):
    """
    14.16: Per-tenant dashboard.
    Acceptance: Tenant sees only own metrics; cross-tenant inspection is blocked.
    """
    dashboard = PerTenantDashboard(signoz_adapter=populated_signoz)

    # Tenant Alpha inspecting Tenant Alpha -> Allowed
    alpha_metrics = dashboard.get_tenant_metrics(
        target_tenant_id="tenant_alpha",
        requesting_tenant_id="tenant_alpha",
    )
    assert alpha_metrics.tenant_id == "tenant_alpha"
    assert alpha_metrics.request_count == 2
    assert alpha_metrics.total_tokens == 250
    assert alpha_metrics.total_cost_usd == pytest.approx(0.005, rel=1e-3)
    assert alpha_metrics.error_count == 1
    assert "claude-3-5-sonnet" in alpha_metrics.models_breakdown

    # Tenant Alpha trying to inspect Tenant Beta -> BLOCKED by isolation
    with pytest.raises(PermissionError, match="Tenant isolation violation"):
        dashboard.get_tenant_metrics(
            target_tenant_id="tenant_beta",
            requesting_tenant_id="tenant_alpha",
            is_admin=False,
        )

    # Admin inspecting Tenant Beta -> Allowed
    beta_metrics = dashboard.get_tenant_metrics(
        target_tenant_id="tenant_beta",
        requesting_tenant_id="admin_console",
        is_admin=True,
    )
    assert beta_metrics.tenant_id == "tenant_beta"
    assert beta_metrics.request_count == 1
    assert beta_metrics.total_tokens == 500
    assert beta_metrics.total_cost_usd == pytest.approx(0.015, rel=1e-3)
    assert beta_metrics.error_count == 0


def test_per_app_dashboard(populated_signoz):
    """14.17: Per-app dashboard."""
    posthog = PostHogAdapter()
    posthog.capture("u1", "portfolio_rebalance", properties={"app_id": "finance_ai"})
    posthog.capture("u1", "stock_analysis", properties={"app_id": "finance_ai"})

    dashboard = PerAppDashboard(signoz_adapter=populated_signoz, posthog_adapter=posthog)

    apps = dashboard.list_applications()
    assert "finance_ai" in apps
    assert "health_bot" in apps

    metrics = dashboard.get_app_metrics("finance_ai")
    assert metrics.app_id == "finance_ai"
    assert metrics.total_invocations == 2
    assert metrics.error_count == 1
    assert metrics.features_invoked.get("portfolio_rebalance") == 1
    assert metrics.features_invoked.get("stock_analysis") == 1


def test_executive_dashboard(populated_signoz):
    """14.18: Executive dashboard."""
    dashboard = ExecutiveDashboard(signoz_adapter=populated_signoz)

    summary = dashboard.get_summary(window_hours=24.0)
    assert summary.total_requests == 3
    assert summary.active_tenants_count == 2
    assert summary.total_cost_usd == pytest.approx(0.020, rel=1e-3)
    assert summary.total_tokens_consumed == 750
    assert summary.uptime_percentage >= 99.0

    # Top tenants by spend: tenant_beta spent 0.015, tenant_alpha spent 0.005
    assert len(summary.top_tenants_by_spend) >= 2
    assert summary.top_tenants_by_spend[0]["tenant_id"] == "tenant_beta"
    assert summary.top_tenants_by_spend[0]["spend_usd"] == pytest.approx(0.015, rel=1e-3)
    assert summary.top_tenants_by_spend[1]["tenant_id"] == "tenant_alpha"

