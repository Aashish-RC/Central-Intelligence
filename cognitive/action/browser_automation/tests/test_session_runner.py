"""Tests for BrowserSessionRunner."""

import pytest
from browser_automation.core.models import (
    BrowserAction,
    BrowserActionType,
    BrowserSessionProfile,
)
from browser_automation.runtime.session_runner import BrowserSessionRunner


def test_session_lifecycle_and_actions():
    profile = BrowserSessionProfile(
        is_headless=True,
        incognito=True,
        viewport_width=1920,
        viewport_height=1080,
    )
    runner = BrowserSessionRunner(profile)

    runner.start_session()
    assert runner.is_active is True
    assert runner.current_url == "about:blank"

    # Action 1: Navigate
    nav = BrowserAction(action_type=BrowserActionType.NAVIGATE, url="https://example.com/search")
    obs = runner.execute_action(nav)
    assert obs.current_url == "https://example.com/search"
    assert "search" in obs.page_title.lower()

    # Action 2: Type text
    type_act = BrowserAction(
        action_type=BrowserActionType.TYPE_TEXT,
        target_selector="input#query",
        payload_text="Pheonix Architecture",
    )
    obs = runner.execute_action(type_act)
    assert "state='1 items'" in obs.dom_snippet

    # Action 3: Click
    click_act = BrowserAction(
        action_type=BrowserActionType.CLICK,
        target_selector="button#btn-search",
    )
    obs = runner.execute_action(click_act)
    assert "state='2 items'" in obs.dom_snippet

    runner.close_session()
    assert runner.is_active is False
