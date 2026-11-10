"""Test Suite for OpenMeter Real-Time Token Metering Adapter.
(Layer 13: Features 13.09, 13.10)
"""

import time
import pytest
from control.billing.models import TokenUsageEvent
from control.billing.metering.openmeter_adapter import OpenMeterAdapter


@pytest.fixture
def adapter():
    return OpenMeterAdapter(endpoint_url="http://localhost:8888")


def test_1_cloudevents_schema_generation(adapter):
    """Test 1: Token consumption event generates compliant CloudEvents 1.0 schema."""
    event = TokenUsageEvent(
        user_id="alice",
        tenant_id="tenant_acme",
        app_id="chat_app",
        model="gpt-4o",
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.0025,
    )

    res = adapter.record_event(event, dispatch_remote=False)
    assert res["stored_locally"] is True
    ce = res["cloud_event"]

    assert ce["specversion"] == "1.0"
    assert ce["type"] == "token_consumption"
    assert ce["source"] == "central-intelligence/reasoning"
    assert ce["subject"] == "user:alice"
    assert ce["data"]["total_tokens"] == 150
    assert ce["data"]["cost_usd"] == 0.0025


def test_2_query_user_daily_usage(adapter):
    """Test 2: Query 'how many tokens did Alice use today?' accurately aggregates."""
    now = time.time()
    # 3 events for Alice
    adapter.record_event(
        TokenUsageEvent(user_id="alice", model="claude-3-5-sonnet", prompt_tokens=100, completion_tokens=200, cost_usd=0.005, timestamp=now),
        dispatch_remote=False,
    )
    adapter.record_event(
        TokenUsageEvent(user_id="alice", model="gpt-4o", prompt_tokens=50, completion_tokens=50, cost_usd=0.002, timestamp=now + 10),
        dispatch_remote=False,
    )
    # 1 event for Bob
    adapter.record_event(
        TokenUsageEvent(user_id="bob", model="gpt-4o", prompt_tokens=500, completion_tokens=500, cost_usd=0.02, timestamp=now + 20),
        dispatch_remote=False,
    )

    alice_summary = adapter.query_usage(user_id="alice", since=now - 60)
    assert alice_summary.total_tokens == 400
    assert alice_summary.events_count == 2
    assert alice_summary.by_model["claude-3-5-sonnet"] == 300
    assert alice_summary.by_model["gpt-4o"] == 100
    assert round(alice_summary.total_cost_usd, 4) == 0.007


def test_3_byok_credit_bypass_metering(adapter):
    """Test 3: BYOK usage is tracked in total usage but excluded from billable cost."""
    adapter.record_event(
        TokenUsageEvent(
            user_id="alice",
            model="o3-mini",
            prompt_tokens=1000,
            completion_tokens=2000,
            cost_usd=0.04,
            byok=True,
            billable=False,
        ),
        dispatch_remote=False,
    )
    adapter.record_event(
        TokenUsageEvent(
            user_id="alice",
            model="o3-mini",
            prompt_tokens=500,
            completion_tokens=500,
            cost_usd=0.015,
            byok=False,
            billable=True,
        ),
        dispatch_remote=False,
    )

    summary = adapter.query_usage(user_id="alice")
    assert summary.total_tokens == 4000
    assert summary.byok_tokens == 3000
    assert summary.billable_tokens == 1000
    assert round(summary.billable_cost_usd, 4) == 0.015
    assert round(summary.total_cost_usd, 4) == 0.055


def test_4_tenant_per_app_breakdown(adapter):
    """Test 4: Multi-app breakdown provides separate cost and token metrics per app."""
    tenant = "enterprise_tenant_x"
    adapter.record_event(
        TokenUsageEvent(tenant_id=tenant, app_id="customer_service_bot", prompt_tokens=200, completion_tokens=200, cost_usd=0.006),
        dispatch_remote=False,
    )
    adapter.record_event(
        TokenUsageEvent(tenant_id=tenant, app_id="data_analysis_bot", prompt_tokens=1000, completion_tokens=1000, cost_usd=0.03),
        dispatch_remote=False,
    )

    breakdown = adapter.get_breakdown_by_app(tenant_id=tenant)
    assert "customer_service_bot" in breakdown
    assert "data_analysis_bot" in breakdown
    assert breakdown["customer_service_bot"].total_tokens == 400
    assert breakdown["data_analysis_bot"].total_tokens == 2000

