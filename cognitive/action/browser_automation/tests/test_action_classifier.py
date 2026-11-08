"""Tests for ActionClassifier."""

import pytest
from browser_automation.core.models import ActionRiskLevel, BrowserAction, BrowserActionType
from browser_automation.engine.action_classifier import ActionClassifier


@pytest.fixture
def classifier():
    return ActionClassifier()


def test_classify_safe_actions(classifier):
    nav_action = BrowserAction(
        action_type=BrowserActionType.NAVIGATE,
        url="https://en.wikipedia.org/wiki/Artificial_intelligence",
    )
    risk, reason = classifier.classify_action(nav_action)
    assert risk == ActionRiskLevel.SAFE
    assert reason is None

    scroll_action = BrowserAction(action_type=BrowserActionType.SCROLL)
    risk, _ = classifier.classify_action(scroll_action)
    assert risk == ActionRiskLevel.SAFE

    normal_click = BrowserAction(
        action_type=BrowserActionType.CLICK,
        target_selector="a.nav-link",
    )
    risk, _ = classifier.classify_action(normal_click)
    assert risk == ActionRiskLevel.SAFE


def test_classify_consequential_action_types(classifier):
    checkout = BrowserAction(action_type=BrowserActionType.PAYMENT_CHECKOUT)
    risk, reason = classifier.classify_action(checkout)
    assert risk == ActionRiskLevel.CONSEQUENTIAL
    assert "payment_checkout" in reason

    delete_action = BrowserAction(action_type=BrowserActionType.DELETE_DATA)
    risk, reason = classifier.classify_action(delete_action)
    assert risk == ActionRiskLevel.CONSEQUENTIAL
    assert "delete_data" in reason


def test_classify_consequential_selectors(classifier):
    submit_click = BrowserAction(
        action_type=BrowserActionType.CLICK,
        target_selector="button#confirm-payment-btn",
    )
    risk, reason = classifier.classify_action(submit_click)
    assert risk == ActionRiskLevel.CONSEQUENTIAL
    assert "confirm-payment" in reason

    purge_click = BrowserAction(
        action_type=BrowserActionType.CLICK,
        target_selector="div.purge-account",
    )
    risk, reason = classifier.classify_action(purge_click)
    assert risk == ActionRiskLevel.CONSEQUENTIAL
    assert "purge" in reason


def test_classify_sensitive_inputs(classifier):
    cc_input = BrowserAction(
        action_type=BrowserActionType.TYPE_TEXT,
        target_selector="input#card_num",
        payload_text="4532 1122 3344 5566",
    )
    risk, reason = classifier.classify_action(cc_input)
    assert risk == ActionRiskLevel.CONSEQUENTIAL
    assert "financial or credential" in reason

    pwd_input = BrowserAction(
        action_type=BrowserActionType.TYPE_TEXT,
        target_selector="input[type='password']",
        payload_text="SuperSecretPass123!",
    )
    risk, reason = classifier.classify_action(pwd_input)
    assert risk == ActionRiskLevel.CONSEQUENTIAL
