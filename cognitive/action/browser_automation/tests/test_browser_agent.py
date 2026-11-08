"""Tests for BrowserAgent: Verifies that a browsing task asks before consequential actions."""

import pytest
from browser_automation.core.models import (
    BrowserAction,
    BrowserActionType,
)
from browser_automation.agent.browser_agent import BrowserAgent


def test_browser_agent_safe_task_completes():
    agent = BrowserAgent()
    actions = [
        BrowserAction(action_type=BrowserActionType.NAVIGATE, url="https://news.ycombinator.com"),
        BrowserAction(action_type=BrowserActionType.CLICK, target_selector="a.storylink"),
        BrowserAction(action_type=BrowserActionType.EXTRACT_DOM),
    ]

    report = agent.run_task(
        task_id="t_safe_1",
        goal="Read latest Hacker News story",
        planned_actions=actions,
    )

    assert report.success is True
    assert report.actions_executed == 3
    assert report.confirmations_requested == 0
    assert report.error_message is None


def test_browser_agent_asks_before_consequential_actions():
    """Core Done When Criteria: A browsing task asks before consequential actions."""
    agent = BrowserAgent()
    actions = [
        BrowserAction(action_type=BrowserActionType.NAVIGATE, url="https://store.example.com/cart"),
        BrowserAction(action_type=BrowserActionType.CLICK, target_selector="button#view-items"),
        # Consequential step: Payment checkout
        BrowserAction(
            action_type=BrowserActionType.CLICK,
            target_selector="button#confirm-checkout-btn",
        ),
        # Following steps that should NOT execute until confirmed
        BrowserAction(action_type=BrowserActionType.NAVIGATE, url="https://store.example.com/order-confirmed"),
    ]

    report = agent.run_task(
        task_id="t_consequential_1",
        goal="Purchase item from store",
        planned_actions=actions,
        auto_approve_consequential=False,
    )

    # Verifies that execution halted before consequential step and asked for confirmation
    assert report.success is False
    assert report.confirmations_requested == 1
    assert report.confirmations_approved == 0
    assert report.actions_executed == 2  # Only the first 2 safe actions ran
    assert "requires confirmation" in (report.error_message or "")
    assert "confirm-checkout" in (report.error_message or "")


def test_browser_agent_executes_when_consequential_confirmed():
    agent = BrowserAgent()
    actions = [
        BrowserAction(action_type=BrowserActionType.NAVIGATE, url="https://store.example.com/cart"),
        BrowserAction(
            action_type=BrowserActionType.CLICK,
            target_selector="button#confirm-checkout-btn",
        ),
    ]

    report = agent.run_task(
        task_id="t_confirmed_1",
        goal="Purchase with pre-approval",
        planned_actions=actions,
        auto_approve_consequential=True,
    )

    assert report.success is True
    assert report.confirmations_requested == 1
    assert report.confirmations_approved == 1
    assert report.actions_executed == 2
