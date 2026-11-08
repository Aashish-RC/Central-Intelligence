"""Live tests for BrowserUseAdapter and Playwright with local HTTP server and confirmation interceptor."""

import http.server
import socketserver
import threading
from typing import Generator
import pytest

from browser_automation.core.agent import BrowserUseAdapter, BrowserUseAgent
from browser_automation.core.models import BrowserAction, BrowserActionType

HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
    <title>Pheonix Live Test Portal</title>
</head>
<body>
    <h1>Pheonix Live Test Portal</h1>
    <p id="welcome-text">Welcome to the Pheonix Live Browser Automation test page.</p>

    <div id="content-section">
        <p>This page tests real browser automation, text extraction, and confirmation interceptors.</p>
    </div>

    <!-- Safe buttons (should not pause) -->
    <button id="btn-info">View Details</button>
    <button id="btn-next">Next Page</button>

    <!-- Consequential elements matching: Submit, Delete, Pay, Confirm, Buy -->
    <button id="btn-delete">Delete Item</button>
    <button id="btn-pay">Pay Invoice</button>
    <button id="btn-confirm">Confirm Order</button>
    <button id="btn-buy">Buy Now</button>

    <!-- Form with submit button -->
    <form id="checkout-form" method="POST" action="/submit">
        <input type="text" id="username" name="username" value="test_user" />
        <button type="submit" id="btn-submit">Submit Form</button>
    </form>
</body>
</html>
"""


class StaticServer:
    """Ephemeral background HTTP server serving test HTML pages."""

    def __init__(self, html: str):
        self.html_bytes = html.encode("utf-8")
        self.server: socketserver.TCPServer = None
        self.thread: threading.Thread = None
        self.port: int = 0

    def start(self) -> str:
        html_data = self.html_bytes

        class Handler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html_data)))
                self.end_headers()
                self.wfile.write(html_data)

            def do_POST(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                resp = b"<html><body><h1>Form Submitted Successfully</h1></body></html>"
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, format, *args):
                pass  # suppress logging during test run

        self.server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()


@pytest.fixture(scope="module")
def static_server() -> Generator[str, None, None]:
    server = StaticServer(HTML_CONTENT)
    url = server.start()
    yield url
    server.stop()


@pytest.fixture(scope="module")
def require_playwright_browser() -> None:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
    except Exception as exc:
        pytest.skip(f"Playwright Chromium is not available: {exc}")


# ==============================================================================
# Live Playwright Integration Tests
# ==============================================================================

def test_playwright_open_url_and_extract_page_text(static_server, require_playwright_browser):
    """Live Test: open a real URL and extract page text via Playwright."""
    agent = BrowserUseAgent(use_playwright=True, headless=True)
    try:
        obs = agent.open_page(static_server)
        assert obs.current_url.startswith("http://127.0.0.1:")
        assert obs.page_title == "Pheonix Live Test Portal"

        page_text = agent.extract_text()
        assert "Pheonix Live Test Portal" in page_text
        assert "Welcome to the Pheonix Live Browser Automation test page." in page_text
        assert "View Details" in page_text
    finally:
        agent.close()


def test_playwright_safe_button_clicks_without_pause(static_server, require_playwright_browser):
    """Live Test: clicking an ordinary button (e.g. 'View Details') executes without pausing."""
    agent = BrowserUseAgent(use_playwright=True, headless=True)
    try:
        agent.open_page(static_server)
        safe_action = BrowserAction(
            action_type=BrowserActionType.CLICK,
            target_selector="#btn-info",
        )
        report = agent.step(safe_action, auto_approve=False)
        assert report.success is True
        assert report.confirmations_requested == 0
        assert report.actions_executed == 1
    finally:
        agent.close()


@pytest.mark.parametrize("selector,keyword", [
    ("#btn-delete", "Delete"),
    ("#btn-pay", "Pay"),
    ("#btn-confirm", "Confirm"),
    ("#btn-buy", "Buy"),
])
def test_playwright_confirmation_interceptor_pauses_consequential_buttons(
    static_server, require_playwright_browser, selector, keyword
):
    """Live Test: confirmation interceptor pauses before clicking any element matching Delete, Pay, Confirm, Buy."""
    agent = BrowserUseAgent(use_playwright=True, headless=True)
    try:
        agent.open_page(static_server)

        # 1. Unapproved action must pause and request confirmation
        action = BrowserAction(
            action_type=BrowserActionType.CLICK,
            target_selector=selector,
        )
        report = agent.step(action, auto_approve=False)
        assert report.success is False
        assert report.confirmations_requested == 1
        assert report.confirmations_approved == 0
        assert report.actions_executed == 0
        assert "requires confirmation" in (report.error_message or "")

        # 2. Approved action must execute successfully
        approved_report = agent.step(action, auto_approve=True)
        assert approved_report.success is True
        assert approved_report.confirmations_approved == 1
        assert approved_report.actions_executed == 1
    finally:
        agent.close()


def test_playwright_form_submit_pauses_for_approval_in_live_test(
    static_server, require_playwright_browser
):
    """Done condition: a form submit pauses for approval in the live test."""
    agent = BrowserUseAgent(use_playwright=True, headless=True)
    try:
        agent.open_page(static_server)

        # Form submit action targeting form or submit button
        submit_action = BrowserAction(
            action_type=BrowserActionType.SUBMIT_FORM,
            target_selector="#btn-submit",
        )

        # Must pause for confirmation without approval
        report = agent.step(submit_action, auto_approve=False)
        assert report.success is False
        assert report.confirmations_requested == 1
        assert report.confirmations_approved == 0
        assert report.actions_executed == 0
        assert "requires confirmation" in (report.error_message or "")

        # Executing with approval proceeds through live page
        approved_report = agent.step(submit_action, auto_approve=True)
        assert approved_report.success is True
        assert approved_report.confirmations_approved == 1
        assert approved_report.actions_executed == 1
    finally:
        agent.close()
