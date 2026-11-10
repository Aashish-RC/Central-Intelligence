"""
Tests for Automated Refund Pipeline (Feature 13.12).
"""

import pytest

from control.billing.engine.lago_adapter import LagoAdapter
from control.billing.payments.hyperswitch_adapter import HyperswitchAdapter
from control.billing.refunds.refund_pipeline import (
    ModelCallFailure,
    RefundPipeline,
)


def test_failed_call_due_to_provider_error_tokens_refunded_automatically():
    """
    Acceptance criterion: Failed call due to provider error -> tokens refunded automatically.
    """
    lago = LagoAdapter()
    pipeline = RefundPipeline(lago_adapter=lago)

    customer_id = "cust_provider_outage_01"
    sub = lago.subscribe_customer(customer_id, "pro")

    # Simulate that user previously executed 5,000 tokens
    lago.record_usage(customer_id, 5000)
    assert lago._subscriptions[customer_id].tokens_used_this_period == 5000

    # Model call for 3,000 tokens fails with a 503 Service Unavailable / Overloaded error
    failure = ModelCallFailure(
        call_id="call_fail_503_abc",
        customer_id=customer_id,
        tokens_attempted=3000,
        error_code="503",
        error_message="Upstream provider anthropic is overloaded. Please retry later.",
        model="claude-3-5-sonnet",
    )

    result = pipeline.process_failed_call(failure)

    assert result.status == "refunded"
    assert result.tokens_refunded == 3000
    assert "Automated refund for provider outage" in result.reason

    # Verify Lago usage counter was automatically reduced / credited back
    sub_after = lago._subscriptions[customer_id]
    assert sub_after.tokens_used_this_period == 2000  # 5,000 - 3,000 auto-refunded


def test_client_side_error_does_not_auto_refund():
    lago = LagoAdapter()
    pipeline = RefundPipeline(lago_adapter=lago)

    customer_id = "cust_bad_prompt"
    lago.subscribe_customer(customer_id, "pro")
    lago.record_usage(customer_id, 2000)

    # 400 Bad Request error (e.g. malformed user JSON)
    failure = ModelCallFailure(
        call_id="call_fail_400",
        customer_id=customer_id,
        tokens_attempted=500,
        error_code="400",
        error_message="Bad request: Invalid parameter schema",
    )

    result = pipeline.process_failed_call(failure)
    assert result.status == "skipped_non_provider_error"
    assert result.tokens_refunded == 0

    # Lago tokens not changed
    assert lago._subscriptions[customer_id].tokens_used_this_period == 2000


def test_combined_token_and_hyperswitch_payment_refund():
    lago = LagoAdapter()
    hyperswitch = HyperswitchAdapter()
    pipeline = RefundPipeline(lago_adapter=lago, hyperswitch_adapter=hyperswitch)

    customer_id = "cust_paid_call"
    # User made a $5.00 payment
    payment = hyperswitch.create_payment(amount_cents=500, customer_id=customer_id)

    # Call failed with 500 Internal Server Error
    failure = ModelCallFailure(
        call_id="call_fail_500",
        customer_id=customer_id,
        tokens_attempted=1000,
        error_code="500",
        error_message="Internal server error in model compute engine",
        payment_id=payment.payment_id,
        amount_cents=500,
    )

    result = pipeline.process_failed_call(failure)
    assert result.status == "refunded"
    assert result.tokens_refunded == 1000
    assert result.cents_refunded == 500
    assert result.hyperswitch_refund_id is not None

    # Check that Hyperswitch payment was refunded
    p = hyperswitch.get_payment(payment.payment_id)
    assert p.refunded_cents == 500
    assert p.status == "refunded"

