"""
Unit tests for Operator Analytics & Cross-Tenant Inspection (14.24).
"""

import time
import pytest
from control.identity.operator_console.console import OperatorConsole, InterventionState
from control.observability.admin_console.operator_analytics import (
    OperatorAnalytics,
    UserUsageProfile,
    CrossTenantUsageReport,
)
from control.observability.signoz.signoz_adapter import SigNozAdapter
from control.observability.models import TraceStatus


@pytest.fixture
def populated_telemetry():
    signoz = SigNozAdapter()
    console = OperatorConsole()
    now = time.time()

    # Heavy User in Tenant Alpha
    for i in range(15):
        s = signoz.start_trace("heavy_op", attributes={"tenant_id": "tenant_alpha", "user_id": "heavy_user_1"})
        s.finish(TraceStatus.OK)
    signoz.record_token_usage("heavy_user_1", "tenant_alpha", "claude-3-opus", prompt_tokens=50000, completion_tokens=10000, cost_usd=1.20)

    # Moderate User in Tenant Alpha
    s = signoz.start_trace("light_op", attributes={"tenant_id": "tenant_alpha", "user_id": "normal_user_1"})
    s.finish(TraceStatus.OK)
    signoz.record_token_usage("normal_user_1", "tenant_alpha", "claude-3-haiku", prompt_tokens=200, completion_tokens=50, cost_usd=0.001)

    # Abusive User in Tenant Beta (many errors)
    for i in range(12):
        s = signoz.start_trace("failing_op", attributes={"tenant_id": "tenant_beta", "user_id": "abusive_user_1"})
        # 60% failure rate
        s.finish(TraceStatus.ERROR if i % 2 == 0 or i % 3 == 0 else TraceStatus.OK)
    signoz.record_token_usage("abusive_user_1", "tenant_beta", "gpt-4o", prompt_tokens=1000, completion_tokens=200, cost_usd=0.03)

    return signoz, console


def test_cross_tenant_usage_and_heavy_user_identification(populated_telemetry):
    """
    Acceptance criteria: Admin can view cross-tenant usage patterns and identify heavy users.
    """
    signoz, console = populated_telemetry
    analytics = OperatorAnalytics(signoz_adapter=signoz, operator_console=console)

    report = analytics.get_cross_tenant_usage(window_seconds=3600)
    assert isinstance(report, CrossTenantUsageReport)
    assert report.total_platform_tokens > 60000
    assert report.total_platform_cost_usd > 1.20

    # Verify both tenants are represented
    tenant_ids = [t.tenant_id for t in report.tenants]
    assert "tenant_alpha" in tenant_ids
    assert "tenant_beta" in tenant_ids

    # Verify heavy users identified
    assert len(report.heavy_users) >= 1
    top_user = report.heavy_users[0]
    assert top_user.user_id == "heavy_user_1"
    assert top_user.tenant_id == "tenant_alpha"
    assert top_user.total_tokens >= 60000
    assert top_user.is_heavy_user is True


def test_abuse_detection_and_operator_pause(populated_telemetry):
    """Verify high error rates trigger abuse flag and allow operator intervention."""
    signoz, console = populated_telemetry
    analytics = OperatorAnalytics(signoz_adapter=signoz, operator_console=console)

    report = analytics.get_cross_tenant_usage(window_seconds=3600)
    flagged_ids = [u.user_id for u in report.flagged_abuse_candidates]
    assert "abusive_user_1" in flagged_ids

    # Admin acts to pause abusive user via OperatorConsole
    rec = analytics.pause_abusive_user(
        user_id="abusive_user_1",
        admin_id="secops_admin",
        reason="Anomalous error burst abuse",
    )
    assert rec.state == InterventionState.PAUSED
    assert not console.is_execution_allowed(user_id="abusive_user_1")


def test_operator_console_wire_integration(populated_telemetry):
    """Verify L12 OperatorConsole delegates cleanly to L14 OperatorAnalytics."""
    signoz, console = populated_telemetry
    analytics = OperatorAnalytics(signoz_adapter=signoz, operator_console=console)
    console.get_analytics = lambda: analytics

    report = console.get_cross_tenant_usage()
    assert report.total_platform_tokens > 0

    heavy = console.identify_heavy_users()
    assert len(heavy) >= 1
    assert heavy[0].user_id == "heavy_user_1"

