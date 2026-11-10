"""Test Suite for Lago Quarantined Billing Engine Adapter.
(Layer 13: Features 13.01–13.05, 13.14–13.16)
"""

import pytest
from control.billing.engine import CustomerSubscription, LagoAdapter, PlanDefinition
from control.billing.models import SubscriptionTier


@pytest.fixture
def lago():
    return LagoAdapter()


def test_1_default_plans_configured(lago):
    """Test 1: Default plans Free (10k tokens) and Pro (100k tokens) are defined."""
    free_plan = lago.get_plan("free")
    pro_plan = lago.get_plan("pro")

    assert free_plan is not None
    assert free_plan.monthly_token_quota == 10_000
    assert free_plan.tier == SubscriptionTier.FREE

    assert pro_plan is not None
    assert pro_plan.monthly_token_quota == 100_000
    assert pro_plan.tier == SubscriptionTier.PRO


def test_2_request_entitlement_within_quota(lago):
    """Test 2: User on Free plan with 5k used can request 2k tokens."""
    lago.subscribe_customer(customer_id="alice", plan_code="free")
    lago.record_usage(customer_id="alice", tokens=5_000)

    allowed, reason = lago.check_entitlement(
        customer_id="alice",
        requested_tokens=2_000,
        model="gpt-4o-mini",
    )
    assert allowed is True
    assert reason == "Authorized"


def test_3_request_blocked_when_quota_exhausted(lago):
    """Test 3: User on Free plan is blocked after reaching 10k monthly quota limit."""
    lago.subscribe_customer(customer_id="bob", plan_code="free")
    lago.record_usage(customer_id="bob", tokens=10_000)

    # Attempting to consume 100 tokens should be blocked
    allowed, reason = lago.check_entitlement(
        customer_id="bob",
        requested_tokens=100,
        model="gpt-4o-mini",
    )
    assert allowed is False
    assert "Monthly quota of 10,000 tokens exhausted" in reason


def test_4_model_access_gated_by_tier(lago):
    """Test 4: Free tier user is blocked from calling premium models like o3-mini."""
    lago.subscribe_customer(customer_id="charlie", plan_code="free")

    allowed, reason = lago.check_entitlement(
        customer_id="charlie",
        requested_tokens=100,
        model="o3-mini",
    )
    assert allowed is False
    assert "Model 'o3-mini' is not included in Developer Free Tier entitlements" in reason

    # Upgrade to Pro tier allows o3-mini
    lago.subscribe_customer(customer_id="charlie", plan_code="pro")
    allowed_pro, _ = lago.check_entitlement(
        customer_id="charlie",
        requested_tokens=100,
        model="o3-mini",
    )
    assert allowed_pro is True


def test_5_wallet_credits_allow_overage(lago):
    """Test 5: Top-up wallet credits allow consuming tokens beyond monthly quota."""
    lago.subscribe_customer(customer_id="dave", plan_code="free")
    lago.record_usage(customer_id="dave", tokens=10_000)

    # Blocked initially
    allowed, _ = lago.check_entitlement("dave", requested_tokens=500, model="gemini-1.5-flash")
    assert allowed is False

    # Top-up wallet with $5.00 (500 cents)
    lago.add_credits("dave", amount_cents=500)
    allowed_after, _ = lago.check_entitlement("dave", requested_tokens=500, model="gemini-1.5-flash")
    assert allowed_after is True


def test_6_invoice_generation(lago):
    """Test 6: Invoicing produces valid invoice record linked to subscription."""
    lago.subscribe_customer(customer_id="emma", plan_code="pro")
    lago.record_usage(customer_id="emma", tokens=42_000)

    inv = lago.generate_invoice(customer_id="emma", tenant_id="tenant_alpha")
    assert inv.customer_id == "emma"
    assert inv.amount_cents == 2000
    assert inv.status == "open"
    assert len(inv.line_items) == 2

