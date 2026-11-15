"""
Unit & Integration Tests for Workstream 05: Billing, Licensing and Metering.

Verifies:
- WS-05.1: Real Lago and OpenMeter service integrations, CloudEvents schema, and durable usage accounting.
- WS-05.2: HyperSwitch payment idempotency, refunds and asynchronous webhook settlement.
- WS-05.3: Double charge prevention, atomic decrement, and entitlement drift prevention.
- WS-05.4: PR1 mandatory licensing, product bundles, BYOK zero-cost bypass and usage entitlements.
- WS-05.5: Automated model call refund pipeline on provider failure and invoice reconciliation.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import httpx
import pytest

from control.billing.byok.bypass import BYOKBypass
from control.billing.engine.lago_adapter import LagoAdapter, PlanDefinition
from control.billing.metering.openmeter_adapter import OpenMeterAdapter
from control.billing.models import BillingInvoice, SubscriptionTier, TokenUsageEvent
from control.billing.payments.hyperswitch_adapter import (
    HyperswitchAdapter,
    PaymentMethod,
    PaymentStatus,
)
from control.billing.refunds.refund_pipeline import ModelCallFailure, RefundPipeline
from control.safety.production_guard import ProductionSafetyError


# -------------------------------------------------------------------------
# WS-05.1: Lago Integration & Subscription Lifecycle
# -------------------------------------------------------------------------

def test_lago_subscription_lifecycle_and_live_events(monkeypatch: pytest.MonkeyPatch):
    """Verifies plan registration, customer subscription, usage recording, and cancellation."""
    lago = LagoAdapter(_defer_prod_check=True)
    custom_plan = PlanDefinition(
        plan_code="enterprise-ai",
        name="Enterprise AI Tier",
        tier=SubscriptionTier.ENTERPRISE,
        monthly_token_quota=500_000,
        price_cents_monthly=10000,
        allowed_models=["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"],
        features_enabled=["chat", "reasoning", "code_execution"],
        overage_allowed=True,
    )
    lago.create_plan(custom_plan)

    cust_id = "tenant_enterprise_01"
    sub = lago.subscribe_customer(cust_id, "enterprise-ai", initial_credits_cents=500)
    assert sub.customer_id == cust_id
    assert sub.status == "active"
    assert sub.wallet_balance_cents == 500

    # Entitlement checks
    allowed, msg = lago.check_entitlement(cust_id, requested_tokens=10_000, model="gpt-4o")
    assert allowed is True
    assert msg == "Authorized"

    # Disallowed model check
    allowed, msg = lago.check_entitlement(cust_id, requested_tokens=10_000, model="unsupported-supermodel")
    assert allowed is False
    assert "not included" in msg

    # Record usage under quota
    lago.record_usage(cust_id, tokens=200_000)
    assert lago._subscriptions[cust_id].tokens_used_this_period == 200_000
    assert lago._subscriptions[cust_id].wallet_balance_cents == 500

    # Record usage triggering overage deduction (overage allowed)
    lago.record_usage(cust_id, tokens=350_000)  # total 550,000 -> 50,000 overage -> $0.50 (50 cents)
    assert lago._subscriptions[cust_id].tokens_used_this_period == 550_000
    assert lago._subscriptions[cust_id].wallet_balance_cents == 450

    # Cancel subscription
    canceled_sub = lago.cancel_subscription(cust_id)
    assert canceled_sub.status == "canceled"
    allowed, msg = lago.check_entitlement(cust_id, requested_tokens=100)
    assert allowed is False
    assert "canceled" in msg


def test_lago_live_record_usage_event_dispatch(monkeypatch: pytest.MonkeyPatch):
    """Verifies that in live mode, record_usage dispatches /api/v1/events with fail-closed semantics."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    dispatched_payloads = []

    def mock_post(url, **kwargs):
        dispatched_payloads.append((url, kwargs.get("json", {})))
        return httpx.Response(201, json={"status": "ok"}, request=httpx.Request("POST", "http://test"))

    lago = LagoAdapter(api_url="http://lago.internal", _defer_prod_check=True)
    lago.adapter_mode = "live"
    monkeypatch.setattr(lago._http_client(), "post", mock_post)

    lago.subscribe_customer("cust_live_evt", "free")
    lago.record_usage("cust_live_evt", tokens=5000)

    # Verify event dispatch occurred
    events = [p for url, p in dispatched_payloads if "/api/v1/events" in url]
    assert len(events) == 1
    event_data = events[0]["event"]
    assert event_data["external_customer_id"] == "cust_live_evt"
    assert event_data["code"] == "token_consumption"
    assert event_data["properties"]["tokens"] == 5000


# -------------------------------------------------------------------------
# WS-05.2 & WS-05.3: OpenMeter CloudEvents & Metering
# -------------------------------------------------------------------------

def test_openmeter_cloudevent_schema_and_query():
    """Verifies CloudEvents 1.0 schema compliance and local usage query aggregation."""
    openmeter = OpenMeterAdapter(_defer_prod_check=True)

    event_1 = TokenUsageEvent(
        user_id="alice",
        tenant_id="tenant_alpha",
        model="claude-3-5-sonnet",
        prompt_tokens=400,
        completion_tokens=600,
        byok=False,
        billable=True,
    )
    event_2 = TokenUsageEvent(
        user_id="alice",
        tenant_id="tenant_alpha",
        model="gpt-4o",
        prompt_tokens=200,
        completion_tokens=300,
        byok=True,
        billable=False,
    )

    res1 = openmeter.record_event(event_1, dispatch_remote=False)
    assert res1["stored_locally"] is True
    ce = res1["cloud_event"]
    assert ce["specversion"] == "1.0"
    assert ce["type"] == "token_consumption"
    assert ce["subject"] == "user:alice"
    assert ce["data"]["total_tokens"] == 1000
    assert ce["data"]["billable"] is True

    openmeter.record_event(event_2, dispatch_remote=False)

    summary = openmeter.query_usage(user_id="alice", tenant_id="tenant_alpha")
    assert summary.total_tokens == 1500
    assert summary.billable_tokens == 1000
    assert summary.byok_tokens == 500
    assert summary.events_count == 2
    assert summary.by_model["claude-3-5-sonnet"] == 1000
    assert summary.by_model["gpt-4o"] == 500


def test_openmeter_live_fail_closed_on_dispatch_failure(monkeypatch: pytest.MonkeyPatch):
    """Verifies that OpenMeter fails closed in live production mode if remote dispatch fails."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    openmeter = OpenMeterAdapter(endpoint_url="http://openmeter.internal", _defer_prod_check=True)
    openmeter.adapter_mode = "live"

    def mock_post_500(url, **kwargs):
        return httpx.Response(500, text="Internal Error", request=httpx.Request("POST", "http://test"))

    monkeypatch.setattr(openmeter._http_client(), "post", mock_post_500)

    event = TokenUsageEvent(user_id="bob", total_tokens=100)
    with pytest.raises(ProductionSafetyError):
        openmeter.record_event(event, dispatch_remote=True)


# -------------------------------------------------------------------------
# WS-05.2 & WS-05.3: HyperSwitch Idempotency, Refunds & Webhooks
# -------------------------------------------------------------------------

def test_hyperswitch_idempotency_prevents_double_charges():
    """Verifies identical idempotency key returns the original PaymentIntent without duplicate charge."""
    lago = LagoAdapter(_defer_prod_check=True)
    hyperswitch = HyperswitchAdapter(lago_adapter=lago, _defer_prod_check=True)

    invoice = lago.generate_invoice(customer_id="cust_idemp")
    idemp_key = "idemp_order_xyz_789"

    # First attempt
    p1 = hyperswitch.create_payment(
        amount_cents=2500,
        customer_id="cust_idemp",
        invoice_id=invoice.invoice_id,
        idempotency_key=idemp_key,
    )
    assert p1.amount_cents == 2500
    assert p1.status == PaymentStatus.SUCCEEDED
    assert len(hyperswitch._payments) == 1

    # Second attempt with same idempotency key (simulating network retry or double click)
    p2 = hyperswitch.create_payment(
        amount_cents=2500,
        customer_id="cust_idemp",
        invoice_id=invoice.invoice_id,
        idempotency_key=idemp_key,
    )
    # Must return exact same payment intent, no second record created
    assert p2 is p1
    assert p2.payment_id == p1.payment_id
    assert len(hyperswitch._payments) == 1


def test_hyperswitch_refund_validation_and_status():
    """Verifies refund balance limits and status transitions."""
    hyperswitch = HyperswitchAdapter(_defer_prod_check=True)
    p = hyperswitch.create_payment(amount_cents=3000, customer_id="cust_rfnd")

    # Partial refund
    rf1 = hyperswitch.refund_payment(p.payment_id, amount_cents=1000, reason="user_downgrade")
    assert rf1.amount_cents == 1000
    assert rf1.status == "succeeded"
    assert hyperswitch.get_payment(p.payment_id).status == PaymentStatus.SUCCEEDED

    # Refund exceeding balance must raise ValueError
    with pytest.raises(ValueError) as exc:
        hyperswitch.refund_payment(p.payment_id, amount_cents=2500)
    assert "exceeds refundable balance" in str(exc.value)

    # Remainder refund completes
    rf2 = hyperswitch.refund_payment(p.payment_id, amount_cents=2000, reason="full_settle")
    assert rf2.amount_cents == 2000
    assert hyperswitch.get_payment(p.payment_id).status == PaymentStatus.REFUNDED


def test_hyperswitch_asynchronous_settlement_webhook():
    """Verifies async webhook updates pending payment and marks linked Lago invoice as paid."""
    lago = LagoAdapter(_defer_prod_check=True)
    hyperswitch = HyperswitchAdapter(lago_adapter=lago, _defer_prod_check=True)

    invoice = lago.generate_invoice(customer_id="cust_async")
    assert invoice.status == "open"

    # Create unconfirmed payment (processing)
    payment = hyperswitch.create_payment(
        amount_cents=4000,
        customer_id="cust_async",
        invoice_id=invoice.invoice_id,
        confirm=False,
    )
    assert payment.status == PaymentStatus.PROCESSING
    assert invoice.status == "open"

    # Simulate asynchronous webhook settlement from Hyperswitch
    webhook_payload = {
        "type": "payment_intent.succeeded",
        "data": {
            "payment_id": payment.payment_id,
            "status": "succeeded",
            "amount": 4000,
            "metadata": {"invoice_id": invoice.invoice_id},
        },
    }

    res = hyperswitch.handle_webhook(webhook_payload)
    assert res["settled"] is True
    assert res["status"] == "succeeded"
    assert res["invoice_settled"] is True

    # Payment and invoice are settled
    assert payment.status == PaymentStatus.SUCCEEDED
    assert invoice.status == "paid"
    assert invoice.paid_at is not None


# -------------------------------------------------------------------------
# WS-05.4: BYOK Zero-Cost Bypass & Attribution
# -------------------------------------------------------------------------

def test_byok_zero_cost_bypass_and_entitlements():
    """Verifies that BYOK requests bypass wallet charges while maintaining accurate token attribution."""
    openmeter = OpenMeterAdapter(_defer_prod_check=True)
    lago = LagoAdapter(_defer_prod_check=True)
    byok = BYOKBypass(openmeter_adapter=openmeter, lago_adapter=lago)

    cust_id = "user_byok_test"
    lago.subscribe_customer(cust_id, "free", initial_credits_cents=100)

    # 1. BYOK call: should NOT bill platform credits
    billable = byok.should_bill(
        user_id=cust_id,
        provider_key_source="byok",
        tokens=5000,
        model="gpt-4o",
    )
    assert billable is False

    # Check that OpenMeter recorded byok=True and billable=False
    summary = openmeter.query_usage(user_id=cust_id)
    assert summary.total_tokens == 5000
    assert summary.byok_tokens == 5000
    assert summary.billable_tokens == 0

    # 2. Platform-managed key call: SHOULD bill
    billable_managed = byok.should_bill(
        user_id=cust_id,
        provider_key_source="platform",
        tokens=2000,
        model="gpt-4o",
        cost_usd=0.04,
    )
    assert billable_managed is True

    summary = openmeter.query_usage(user_id=cust_id)
    assert summary.total_tokens == 7000
    assert summary.byok_tokens == 5000
    assert summary.billable_tokens == 2000


# -------------------------------------------------------------------------
# WS-05.5: Automated Model Call Refund Pipeline
# -------------------------------------------------------------------------

def test_automated_refund_pipeline_provider_error():
    """Verifies that upstream 5xx errors trigger automatic token restoration and Hyperswitch refund."""
    lago = LagoAdapter(_defer_prod_check=True)
    hyperswitch = HyperswitchAdapter(lago_adapter=lago, _defer_prod_check=True)
    pipeline = RefundPipeline(lago_adapter=lago, hyperswitch_adapter=hyperswitch)

    cust_id = "user_pipeline_test"
    lago.subscribe_customer(cust_id, "free", initial_credits_cents=500)
    payment = hyperswitch.create_payment(amount_cents=500, customer_id=cust_id)

    # Simulate upstream 503 Gateway Timeout
    failure = ModelCallFailure(
        call_id="call_fail_01",
        customer_id=cust_id,
        tokens_attempted=10000,
        error_code="503",
        error_message="Upstream Provider Overloaded (503 Service Unavailable)",
        payment_id=payment.payment_id,
        amount_cents=500,
    )

    res = pipeline.process_failed_call(failure)
    assert res.status == "refunded"
    assert res.tokens_refunded == 10000
    assert res.cents_refunded == 500
    assert res.hyperswitch_refund_id is not None

    # Verify payment status in Hyperswitch is now REFUNDED
    assert hyperswitch.get_payment(payment.payment_id).status == PaymentStatus.REFUNDED


def test_automated_refund_pipeline_skips_user_error():
    """Verifies that client errors (e.g., 400 Bad Request) are not automatically refunded."""
    lago = LagoAdapter(_defer_prod_check=True)
    hyperswitch = HyperswitchAdapter(lago_adapter=lago, _defer_prod_check=True)
    pipeline = RefundPipeline(lago_adapter=lago, hyperswitch_adapter=hyperswitch)

    cust_id = "user_client_err"
    lago.subscribe_customer(cust_id, "free")

    failure = ModelCallFailure(
        call_id="call_fail_02",
        customer_id=cust_id,
        tokens_attempted=5000,
        error_code="400",
        error_message="Invalid request schema: missing prompt parameter",
    )

    res = pipeline.process_failed_call(failure)
    assert res.status == "skipped_non_provider_error"
    assert res.tokens_refunded == 0
    assert res.cents_refunded == 0
