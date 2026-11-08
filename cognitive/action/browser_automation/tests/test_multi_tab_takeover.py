"""Unit tests for Multi-Tab Browser Management & Takeover Subsystem."""

from browser_automation.core.agent import BrowserUseAgent
from browser_automation.core.models import BrowserAction, BrowserActionType
from browser_automation.core.multi_tab import TabManager
from browser_automation.core.takeover import TakeoverManager, TakeoverStatus, TakeoverTrigger
from browser_automation.runtime.session_runner import BrowserSessionRunner


def test_tab_manager_lifecycle():
    manager = TabManager(initial_url="https://example.com/home", initial_title="Home")
    tabs = manager.list_tabs()
    assert len(tabs) == 1
    assert tabs[0].url == "https://example.com/home"
    assert tabs[0].is_active is True

    # Open a second tab
    tab2 = manager.open_tab(url="https://example.com/docs", title="Docs", set_active=True)
    assert len(manager.list_tabs()) == 2
    assert manager.get_active_tab().tab_id == tab2.tab_id
    assert tabs[0].is_active is False

    # Switch back to first tab
    switched = manager.switch_tab(tabs[0].tab_id)
    assert switched.is_active is True
    assert manager.get_active_tab().tab_id == tabs[0].tab_id

    # Close second tab
    assert manager.close_tab(tab2.tab_id) is True
    assert len(manager.list_tabs()) == 1

    # Closing last tab does not delete, resets to blank
    assert manager.close_tab(tabs[0].tab_id) is True
    assert len(manager.list_tabs()) == 1
    assert manager.get_active_tab().url == "about:blank"


def test_browser_agent_multi_tab_navigation():
    runner = BrowserSessionRunner()
    agent = BrowserUseAgent(session_runner=runner)

    # Initial page
    obs1 = agent.open_page("https://example.com/login")
    assert obs1.current_url == "https://example.com/login"

    # Open new tab
    obs2 = agent.open_tab("https://example.com/dashboard", title="Dashboard")
    assert obs2.current_url == "https://example.com/dashboard"
    assert len(agent.tab_manager.list_tabs()) == 2


def test_multi_tab_takeover_and_tab_switching():
    manager = TakeoverManager()
    runner = BrowserSessionRunner()
    agent = BrowserUseAgent(session_runner=runner, takeover_manager=manager)

    # Tab 1: safe page
    agent.open_page("https://example.com/public")

    # Tab 2: protected CAPTCHA page
    agent.open_tab("https://example.com/protected", title="Protected Cloudflare")
    runner.custom_dom_snippet = "<div id='cf-turnstile-wrapper'>Turnstile verification required</div>"

    action = BrowserAction(
        action_type=BrowserActionType.CLICK,
        target_selector="#verify-btn",
    )

    # Trigger action - should pause with multi-tab takeover payload
    report = agent.step(action)
    assert report.success is False
    assert report.extracted_data.get("takeover_required") is True
    req_id = report.extracted_data.get("request_id")
    assert req_id is not None

    req = manager.get_active_takeover(runner.profile.session_id)
    assert req is not None
    assert req.active_tab_id is not None
    assert len(req.tabs) == 2

    # Operator switches tabs inside the active takeover
    tab1_id = req.tabs[0].tab_id
    switched_req = manager.switch_takeover_tab(req_id, tab1_id)
    assert switched_req.active_tab_id == tab1_id

    # Resolve takeover
    res = agent.resolve_takeover_and_resume(req_id, user_notes="Solved CAPTCHA on tab 2")
    assert res.success is True
    assert manager.get_active_takeover(runner.profile.session_id) is None
