"""
Tests for BYOK Credit Bypass (Features 13.06, 13.10).
"""

import pytest

from control.billing.byok.bypass import BYOKBypass
from control.billing.engine.lago_adapter import LagoAdapter
from control.billing.metering.openmeter_adapter import OpenMeterAdapter


def test_byok_user_uses_tokens_but_is_not_billed_quota_still_tracked():
    """
    Acceptance criterion: BYOK user uses tokens but isn't billed; quota still tracked.
    """
    openmeter = OpenMeterAdapter()
    lago = LagoAdapter()
    bypass = BYOKBypass(openmeter_adapter=openmeter, lago_adapter=lago)

    user_id = "user_byok_tester_01"
    sub = lago.subscribe_customer(user_id, "free")
    initial_tokens_used = sub.tokens_used_this_period

    # 1. User executes call with BYOK API key (5,000 tokens)
    should_bill = bypass.should_bill(
        user_id=user_id,
        provider_key_source="byok",
        tokens=5000,
        model="gpt-4o",
    )

    # Must NOT bill the user
    assert should_bill is False

    # Lago subscription tokens used must NOT increase (bypassed platform billing)
    sub_after = lago._subscriptions[user_id]
    assert sub_after.tokens_used_this_period == initial_tokens_used

    # Quota still tracked in internal quota monitor
    usage = bypass.get_user_usage(user_id)
    assert usage["total"] == 5000
    assert usage["byok"] == 5000
    assert usage["billable"] == 0

    # OpenMeter received event with byok=True, billable=False
    assert len(openmeter._local_events) == 1
    last_event = openmeter._local_events[-1]
    assert last_event.user_id == user_id
    assert last_event.byok is True
    assert last_event.billable is False
    assert last_event.total_tokens == 5000
    assert last_event.cost_usd == 0.0


def test_platform_key_bills_normally():
    openmeter = OpenMeterAdapter()
    lago = LagoAdapter()
    bypass = BYOKBypass(openmeter_adapter=openmeter, lago_adapter=lago)

    user_id = "user_platform_billing"
    lago.subscribe_customer(user_id, "free")

    # User executes call using platform-hosted key
    should_bill = bypass.should_bill(
        user_id=user_id,
        provider_key_source="platform",
        tokens=2000,
        model="claude-3-5-sonnet",
        cost_usd=0.03,
    )

    assert should_bill is True

    # Lago usage was incremented
    sub = lago._subscriptions[user_id]
    assert sub.tokens_used_this_period == 2000

    # OpenMeter received billable=True event
    assert len(openmeter._local_events) == 1
    event = openmeter._local_events[-1]
    assert event.byok is False
    assert event.billable is True
    assert event.total_tokens == 2000
    assert event.cost_usd == 0.03

    usage = bypass.get_user_usage(user_id)
    assert usage["total"] == 2000
    assert usage["billable"] == 2000
    assert usage["byok"] == 0


def test_mixed_byok_and_platform_usage_tracking():
    openmeter = OpenMeterAdapter()
    lago = LagoAdapter()
    bypass = BYOKBypass(openmeter_adapter=openmeter, lago_adapter=lago)

    user_id = "user_hybrid"
    lago.subscribe_customer(user_id, "pro")

    # Call 1: 3,000 tokens on BYOK
    bypass.should_bill(user_id, "byok", tokens=3000)
    # Call 2: 1,500 tokens on Platform
    bypass.should_bill(user_id, "platform", tokens=1500)

    usage = bypass.get_user_usage(user_id)
    assert usage["total"] == 4500
    assert usage["byok"] == 3000
    assert usage["billable"] == 1500

    # Only 1500 was billed to Lago
    sub = lago._subscriptions[user_id]
    assert sub.tokens_used_this_period == 1500

