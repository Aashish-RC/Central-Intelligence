"""Browser Use Automation Adapter and Security Interceptor Agent with Playwright integration."""

import re
from typing import Callable, Dict, List, Optional
from ..agent.browser_agent import BrowserAgent
from ..core.interfaces import BaseBrowserSessionRunner, BaseConfirmationGate
from ..core.models import (
    ActionRiskLevel,
    BrowserAction,
    BrowserActionType,
    BrowserObservation,
    BrowserSessionProfile,
    BrowserTaskReport,
    ConfirmationStatus,
    utc_now,
)
from ..engine.confirmation_rules import ConfirmationRulesGate
from ..runtime.session_runner import BrowserSessionRunner
from .multi_tab import TabInfo, TabManager
from .takeover import CaptchaDetector, TakeoverManager, TakeoverRequest, TakeoverTrigger

INTERCEPTOR_BUTTON_REGEX = re.compile(
    r"\b(submit|delete|pay|confirm|buy|checkout|purchase|remove|cancel-subscription)\b",
    re.IGNORECASE,
)


class BrowserUseAdapter:
    """Adapter for Playwright Chromium headless automation with security interceptor."""

    def __init__(
        self,
        headless: bool = True,
        interceptor_callback: Optional[Callable[[BrowserAction], bool]] = None,
        use_playwright: bool = False,
    ):
        self.headless = headless
        self.use_playwright = use_playwright
        self.interceptor_callback = interceptor_callback or self._default_security_interceptor
        self._playwright = None
        self._browser = None
        self._page = None

    @staticmethod
    def is_playwright_installed() -> bool:
        """Check whether playwright is installed in the python environment."""
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            return False

    def _ensure_browser(self):
        """Lazily initialize Playwright browser and page on demand."""
        if self._page is not None and not self._page.is_closed():
            return self._page

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Playwright is not installed. Install with 'pip install playwright' "
                "or install the 'browser' optional dependencies."
            ) from e

        if self._playwright is None:
            self._playwright = sync_playwright().start()

        if self._browser is None:
            self._browser = self._playwright.chromium.launch(headless=self.headless)

        self._page = self._browser.new_page()
        return self._page

    def open_url(self, url: str) -> str:
        """Opens target URL in Playwright and returns page title."""
        page = self._ensure_browser()
        page.goto(url, wait_until="domcontentloaded")
        return page.title()

    def get_page_text(self) -> str:
        """Extracts visible body text content from the active page."""
        if self._page is None or self._page.is_closed():
            return ""
        try:
            return self._page.inner_text("body")
        except Exception:
            try:
                return self._page.content()
            except Exception:
                return ""

    def get_element_text(self, selector: Optional[str]) -> str:
        """Extracts visible text, value, or label from an element by selector."""
        if not selector or self._page is None or self._page.is_closed():
            return ""
        try:
            elem = self._page.query_selector(selector)
            if not elem:
                return ""
            text = (elem.inner_text() or "").strip()
            if not text:
                text = (elem.get_attribute("value") or "").strip()
            if not text:
                text = (elem.get_attribute("aria-label") or "").strip()
            return text
        except Exception:
            return ""

    def click(self, selector: str) -> None:
        """Clicks an element in the active page."""
        page = self._ensure_browser()
        page.click(selector)

    def fill(self, selector: str, text: str) -> None:
        """Fills text into an input field in the active page."""
        page = self._ensure_browser()
        page.fill(selector, text)

    def get_current_url(self) -> str:
        """Returns the current URL of the active page."""
        if self._page and not self._page.is_closed():
            return self._page.url
        return ""

    def close(self) -> None:
        """Cleanly closes page, browser, and playwright instance."""
        if self._page:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None

        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def is_consequential_action(self, action: BrowserAction) -> bool:
        """Determines if an action or targeted element requires human confirmation."""
        # 1. Action type check
        if action.action_type in (
            BrowserActionType.SUBMIT_FORM,
            BrowserActionType.PAYMENT_CHECKOUT,
            BrowserActionType.DELETE_DATA,
        ):
            return True

        # 2. Selector and payload regex check
        target = f"{action.target_selector or ''} {action.payload_text or ''}".lower()
        if INTERCEPTOR_BUTTON_REGEX.search(target):
            return True

        # 3. Live DOM element text check (matches Submit, Delete, Pay, Confirm, Buy)
        if action.action_type == BrowserActionType.CLICK and action.target_selector:
            elem_text = self.get_element_text(action.target_selector)
            if elem_text and INTERCEPTOR_BUTTON_REGEX.search(elem_text):
                return True

        return False

    def _default_security_interceptor(self, action: BrowserAction) -> bool:
        """Default security interceptor: returns False (blocks/pauses) for consequential actions."""
        return not self.is_consequential_action(action)


class BrowserUseAgent(BrowserAgent):
    """High-level Browser Use Agent with interactive page opening, text extraction, and form gating."""

    def __init__(
        self,
        session_runner: Optional[BaseBrowserSessionRunner] = None,
        confirmation_gate: Optional[BaseConfirmationGate] = None,
        adapter: Optional[BrowserUseAdapter] = None,
        use_playwright: bool = False,
        headless: bool = True,
        takeover_manager: Optional[TakeoverManager] = None,
        tab_manager: Optional[TabManager] = None,
    ):
        super().__init__(
            session_runner=session_runner,
            confirmation_gate=confirmation_gate,
        )
        self.use_playwright = use_playwright or (adapter.use_playwright if adapter else False)
        self.adapter = adapter or BrowserUseAdapter(
            headless=headless,
            use_playwright=self.use_playwright,
        )
        self.takeover_manager = takeover_manager or TakeoverManager()
        self.tab_manager = tab_manager or TabManager()

    def open_page(self, url: str) -> BrowserObservation:
        """Opens target URL in browser and returns initial observation."""
        if self.use_playwright:
            title = self.adapter.open_url(url)
            text = self.adapter.get_page_text()
            obs = BrowserObservation(
                current_url=self.adapter.get_current_url() or url,
                page_title=title,
                dom_snippet=text,
                status_code=200,
                screenshot_id="playwright_page",
                captured_at=utc_now(),
            )
            # Synchronize session runner metadata
            self.runner.current_url = obs.current_url
            self.runner.page_title = obs.page_title
            active_tab = self.tab_manager.get_active_tab()
            self.tab_manager.update_tab(active_tab.tab_id, url=obs.current_url, title=obs.page_title)
            return obs

        action = BrowserAction(action_type=BrowserActionType.NAVIGATE, url=url)
        obs = self.runner.execute_action(action)
        active_tab = self.tab_manager.get_active_tab()
        self.tab_manager.update_tab(active_tab.tab_id, url=obs.current_url, title=obs.page_title)
        return obs

    def open_tab(self, url: str = "about:blank", title: str = "New Tab") -> BrowserObservation:
        """Opens a new browser tab in the active session and navigates to target URL."""
        self.tab_manager.open_tab(url=url, title=title, set_active=True)
        return self.open_page(url)

    def switch_tab(self, tab_id: str) -> BrowserObservation:
        """Switches focus to an existing tab by its ID."""
        tab = self.tab_manager.switch_tab(tab_id)
        self.runner.current_url = tab.url
        self.runner.page_title = tab.title
        return self.runner.get_current_observation()

    def extract_text(self) -> str:
        """Extracts text content from the current page."""
        if self.use_playwright:
            text = self.adapter.get_page_text()
            if text:
                return text
        obs = self.runner.get_current_observation()
        return obs.dom_snippet

    def resolve_takeover_and_resume(
        self,
        request_id: str,
        action: Optional[BrowserAction] = None,
        operator_id: str = "human_user",
        user_notes: Optional[str] = None,
    ) -> BrowserTaskReport:
        """Resolves human takeover and resumes automated execution."""
        req = self.takeover_manager.resolve_takeover(request_id, user_notes=user_notes, operator_id=operator_id)
        if action:
            return self.step(action, auto_approve=True)
        obs = self.runner.get_current_observation()
        return BrowserTaskReport(
            task_id=req.request_id,
            goal="Resume after human takeover",
            actions_executed=1,
            confirmations_requested=1,
            confirmations_approved=1,
            success=True,
            final_url=obs.current_url,
            extracted_data={"takeover_resolved": True, "request_id": req.request_id, "resolved_by": operator_id},
        )

    def step(
        self,
        action: BrowserAction,
        auto_approve: bool = False,
    ) -> BrowserTaskReport:
        """Executes a single browser step with confirmation pause on form submit or consequential buttons."""
        obs = self.runner.get_current_observation()
        current_url = self.adapter.get_current_url() if self.use_playwright else obs.current_url

        # Check for CAPTCHA / bot challenge
        challenge = CaptchaDetector.detect(obs.dom_snippet)
        if challenge and not auto_approve:
            active_tab = self.tab_manager.get_active_tab()
            req = self.takeover_manager.request_takeover(
                session_id=self.runner.profile.session_id,
                trigger=TakeoverTrigger.CAPTCHA_DETECTED,
                reason=f"Verification barrier detected: {challenge}",
                url=current_url,
                challenge_type=challenge,
                dom_context=obs.dom_snippet[:400],
                active_tab_id=active_tab.tab_id,
                tabs=self.tab_manager.list_tabs(),
            )
            return BrowserTaskReport(
                task_id=action.action_id,
                goal=f"Execute {action.action_type.value}",
                actions_executed=0,
                confirmations_requested=1,
                confirmations_approved=0,
                success=False,
                final_url=current_url,
                error_message=f"Human takeover required: {challenge} challenge detected. Request ID: {req.request_id}",
                extracted_data={"takeover_required": True, "challenge_type": challenge, "request_id": req.request_id},
                action_log=[action],
            )

        # Check adapter security interceptor
        is_safe = self.adapter.interceptor_callback(action)
        allowed_by_gate = self.gate.evaluate_and_gate(action, current_url=current_url)

        if not is_safe or not allowed_by_gate:
            if not auto_approve:
                elem_text = self.adapter.get_element_text(action.target_selector) if self.use_playwright else ""
                desc = f" (element text: '{elem_text}')" if elem_text else ""
                return BrowserTaskReport(
                    task_id=action.action_id,
                    goal=f"Execute {action.action_type.value}",
                    actions_executed=0,
                    confirmations_requested=1,
                    confirmations_approved=0,
                    success=False,
                    final_url=current_url,
                    error_message=(
                        f"Task paused: Consequential action '{action.action_type.value}' on target "
                        f"'{action.target_selector or action.url}'{desc} requires confirmation."
                    ),
                    action_log=[action],
                )
            else:
                self.gate.approve_action(action.action_id)

        # Execute safe or approved action
        if self.use_playwright:
            if action.action_type == BrowserActionType.NAVIGATE and action.url:
                self.adapter.open_url(action.url)
            elif action.action_type == BrowserActionType.CLICK and action.target_selector:
                self.adapter.click(action.target_selector)
            elif action.action_type == BrowserActionType.TYPE_TEXT and action.target_selector and action.payload_text:
                self.adapter.fill(action.target_selector, action.payload_text)
            elif action.action_type == BrowserActionType.SUBMIT_FORM and action.target_selector:
                self.adapter.click(action.target_selector)

            final_url = self.adapter.get_current_url()
            page_text = self.adapter.get_page_text()
            title = self.adapter._page.title() if self.adapter._page else ""
            return BrowserTaskReport(
                task_id=action.action_id,
                goal=f"Execute {action.action_type.value}",
                actions_executed=1,
                confirmations_requested=0 if is_safe else 1,
                confirmations_approved=0 if is_safe else 1,
                success=True,
                final_url=final_url,
                extracted_data={"title": title, "snippet": page_text},
                action_log=[action],
            )

        # Fallback to simulated runner
        self.runner.execute_action(action)
        final_obs = self.runner.get_current_observation()
        return BrowserTaskReport(
            task_id=action.action_id,
            goal=f"Execute {action.action_type.value}",
            actions_executed=1,
            confirmations_requested=0 if is_safe else 1,
            confirmations_approved=0 if is_safe else 1,
            success=True,
            final_url=final_obs.current_url,
            extracted_data={"title": final_obs.page_title, "snippet": final_obs.dom_snippet},
            action_log=[action],
        )

    def close(self) -> None:
        """Close browser resources."""
        if self.adapter:
            self.adapter.close()
        self.runner.close_session()


__all__ = [
    "BrowserAgent",
    "BrowserUseAgent",
    "BrowserUseAdapter",
    "INTERCEPTOR_BUTTON_REGEX",
    "CaptchaDetector",
    "TakeoverManager",
    "TakeoverRequest",
    "TakeoverTrigger",
    "TabInfo",
    "TabManager",
]
