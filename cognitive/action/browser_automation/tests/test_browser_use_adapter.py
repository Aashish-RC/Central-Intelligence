"""Unit tests for BrowserUseAgent and security interceptor callback."""

import pytest
from browser_automation.core.agent import BrowserUseAgent, BrowserUseAdapter
from browser_automation.core.models import BrowserAction, BrowserActionType


def test_browser_use_agent_open_page_and_extract_text():
    agent = BrowserUseAgent()
    obs = agent.open_page("https://example.com/research")
    assert obs.current_url == "https://example.com/research"
    assert "example.com" in obs.current_url

    text = agent.extract_text()
    assert "<html>" in text
    assert "https://example.com/research" in text


def test_browser_use_agent_pauses_on_form_submit():
    agent = BrowserUseAgent()
    agent.open_page("https://example.com/contact")

    # Form submission action
    submit_action = BrowserAction(
        action_type=BrowserActionType.SUBMIT_FORM,
        target_selector="form#contact-form",
    )

    # Attempt step without approval -> must pause and request confirmation
    report = agent.step(submit_action, auto_approve=False)
    assert report.success is False
    assert report.actions_executed == 0
    assert report.confirmations_requested == 1
    assert "requires confirmation" in (report.error_message or "")


@pytest.mark.parametrize("target_button", [
    "button#submit-order",
    "button.btn-delete-account",
    "button#pay-invoice",
    "button.confirm-transfer",
])
def test_browser_use_agent_pauses_on_consequential_buttons(target_button):
    agent = BrowserUseAgent()
    agent.open_page("https://app.example.com/dashboard")

    click_action = BrowserAction(
        action_type=BrowserActionType.CLICK,
        target_selector=target_button,
    )

    report = agent.step(click_action, auto_approve=False)
    assert report.success is False
    assert report.confirmations_requested == 1
    assert "requires confirmation" in (report.error_message or "")


def test_browser_use_agent_executes_when_approved():
    agent = BrowserUseAgent()
    agent.open_page("https://app.example.com/dashboard")

    click_action = BrowserAction(
        action_type=BrowserActionType.CLICK,
        target_selector="button#pay-invoice",
    )

    # With approval
    report = agent.step(click_action, auto_approve=True)
    assert report.success is True
    assert report.actions_executed == 1
    assert report.confirmations_approved == 1
