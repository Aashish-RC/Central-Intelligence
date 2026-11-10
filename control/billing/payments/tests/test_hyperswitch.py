"""
Tests for Hyperswitch Universal Payment Router Adapter (Feature 13.13).
"""

import pytest

from control.billing.engine.lago_adapter import LagoAdapter
from control.billing.payments.hyperswitch_adapter import (
    HyperswitchAdapter,
    PaymentMethod,
    PaymentStatus,
)


def test_process_ten_dollar_test_payment_via_stripe_linked_to_lago_invoice():
    """
    Acceptance criterion: Process $10 test payment via Stripe test mode; linked to Lago invoice.
    """
    lago = LagoAdapter()
    hyperswitch = HyperswitchAdapter(lago_adapter=lago)

    customer_id = "cust_stripe_test_10"
    lago.subscribe_customer(customer_id, "free")

    # Generate Lago invoice
    invoice = lago.generate_invoice(customer_id=customer_id)
    invoice.amount_cents = 1000  # $10.00
    assert invoice.status == "open"

    # Process $10 payment through Hyperswitch via Stripe test gateway
    payment = hyperswitch.create_payment(
        amount_cents=1000,
        currency="USD",
        customer_id=customer_id,
        invoice_id=invoice.invoice_id,
        gateway="stripe",
        payment_method=PaymentMethod.CARD,
        confirm=True,
    )

    assert payment.amount_cents == 1000
    assert payment.currency == "USD"
    assert payment.gateway == "stripe"
    assert payment.invoice_id == invoice.invoice_id
    assert payment.status == PaymentStatus.SUCCEEDED

    # Verify Lago invoice is now settled & marked paid
    assert invoice.status == "paid"
    assert invoice.paid_at is not None


def test_process_invoice_payment_helper():
    lago = LagoAdapter()
    hyperswitch = HyperswitchAdapter(lago_adapter=lago)

    customer_id = "cust_pro_subscriber"
    lago.subscribe_customer(customer_id, "pro")

    invoice = lago.generate_invoice(customer_id=customer_id)
    assert invoice.amount_cents == 2000  # $20.00 Pro tier

    # Use process_invoice_payment helper
    intent = hyperswitch.process_invoice_payment(invoice, gateway="stripe")
    assert intent.status == PaymentStatus.SUCCEEDED
    assert intent.amount_cents == 2000
    assert invoice.status == "paid"


def test_paypal_gateway_routing():
    hyperswitch = HyperswitchAdapter()
    payment = hyperswitch.create_payment(
        amount_cents=500,
        customer_id="cust_paypal",
        gateway="paypal",
        payment_method=PaymentMethod.PAYPAL,
    )
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.gateway == "paypal"
    assert payment.payment_method == PaymentMethod.PAYPAL


def test_refund_processing():
    hyperswitch = HyperswitchAdapter()
    payment = hyperswitch.create_payment(
        amount_cents=5000,
        customer_id="cust_refund_test",
        gateway="stripe",
    )

    # Partial refund of $20
    refund1 = hyperswitch.refund_payment(payment.payment_id, amount_cents=2000, reason="partial_credit")
    assert refund1.amount_cents == 2000
    assert refund1.status == "succeeded"

    p_after_1 = hyperswitch.get_payment(payment.payment_id)
    assert p_after_1.refunded_cents == 2000
    assert p_after_1.status == PaymentStatus.SUCCEEDED

    # Remainder refund of $30
    refund2 = hyperswitch.refund_payment(payment.payment_id, amount_cents=3000, reason="full_settlement")
    assert refund2.amount_cents == 3000

    p_after_2 = hyperswitch.get_payment(payment.payment_id)
    assert p_after_2.refunded_cents == 5000
    assert p_after_2.status == PaymentStatus.REFUNDED

