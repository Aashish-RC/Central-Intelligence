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


def test_live_payment_network_timeout_fails_closed(monkeypatch: pytest.MonkeyPatch):
    import httpx
    from control.safety.production_guard import ProductionSafetyError

    monkeypatch.setenv("HYPERSWITCH_MODE", "live")
    hyperswitch = HyperswitchAdapter(api_key="real_live_key_12345")

    def mock_post_timeout(*args, **kwargs):
        raise httpx.ConnectTimeout("Connection to hyperswitch:8080 timed out")

    monkeypatch.setattr(httpx.Client, "post", mock_post_timeout)

    with pytest.raises(ProductionSafetyError) as exc_info:
        hyperswitch.create_payment(amount_cents=1000, confirm=True)
    assert "Live payment execution failed" in str(exc_info.value)


def test_live_payment_http_error_fails_closed(monkeypatch: pytest.MonkeyPatch):
    import httpx
    from control.safety.production_guard import ProductionSafetyError

    monkeypatch.setenv("HYPERSWITCH_MODE", "live")
    hyperswitch = HyperswitchAdapter(api_key="real_live_key_12345")

    def mock_post_500(*args, **kwargs):
        return httpx.Response(500, text="Internal Gateway Error", request=httpx.Request("POST", "http://test"))

    monkeypatch.setattr(httpx.Client, "post", mock_post_500)

    with pytest.raises(ProductionSafetyError) as exc_info:
        hyperswitch.create_payment(amount_cents=1000, confirm=True)
    assert "Hyperswitch payment API returned HTTP 500" in str(exc_info.value)


def test_live_payment_malformed_response_fails_closed(monkeypatch: pytest.MonkeyPatch):
    import httpx
    from control.safety.production_guard import ProductionSafetyError

    monkeypatch.setenv("HYPERSWITCH_MODE", "live")
    hyperswitch = HyperswitchAdapter(api_key="real_live_key_12345")

    def mock_post_bad_json(*args, **kwargs):
        return httpx.Response(200, text="NOT_JSON_HTML_ERROR", request=httpx.Request("POST", "http://test"))

    monkeypatch.setattr(httpx.Client, "post", mock_post_bad_json)

    with pytest.raises(ProductionSafetyError) as exc_info:
        hyperswitch.create_payment(amount_cents=1000, confirm=True)
    assert "malformed non-JSON response" in str(exc_info.value)


def test_live_payment_declined_state_does_not_settle_invoice(monkeypatch: pytest.MonkeyPatch):
    import httpx

    monkeypatch.setenv("HYPERSWITCH_MODE", "live")
    lago = LagoAdapter()
    hyperswitch = HyperswitchAdapter(api_key="real_live_key_12345", lago_adapter=lago)

    customer_id = "cust_declined_test"
    lago.subscribe_customer(customer_id, "free")
    invoice = lago.generate_invoice(customer_id=customer_id)
    assert invoice.status == "open"

    def mock_post_declined(*args, **kwargs):
        return httpx.Response(
            200,
            json={"payment_id": "pay_declined_123", "status": "failed"},
            request=httpx.Request("POST", "http://test"),
        )

    monkeypatch.setattr(httpx.Client, "post", mock_post_declined)

    intent = hyperswitch.process_invoice_payment(invoice, gateway="stripe")
    assert intent.status == PaymentStatus.FAILED
    # Crucial: invoice MUST NOT be marked paid!
    assert invoice.status == "open"
    assert invoice.paid_at is None


