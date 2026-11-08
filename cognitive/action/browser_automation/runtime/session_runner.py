"""Browser Session Runner: Manages headless browser profiles and executes approved DOM actions."""

from typing import Dict, List, Optional
from ..core.interfaces import BaseBrowserSessionRunner
from ..core.models import (
    BrowserAction,
    BrowserActionType,
    BrowserObservation,
    BrowserSessionProfile,
    utc_now,
)


class BrowserSessionRunner(BaseBrowserSessionRunner):
    """Executes browser actions within an isolated, headless sandboxed environment."""

    def __init__(self, profile: Optional[BrowserSessionProfile] = None):
        self.profile = profile or BrowserSessionProfile()
        self.current_url: str = "about:blank"
        self.page_title: str = "Blank"
        self.history: List[str] = []
        self.dom_state: Dict[str, str] = {}
        self.is_active: bool = False

    def start_session(
        self, profile: Optional[BrowserSessionProfile] = None
    ) -> BrowserSessionProfile:
        if profile:
            self.profile = profile
        self.is_active = True
        self.current_url = "about:blank"
        self.page_title = "New Tab"
        self.history.clear()
        self.custom_dom_snippet: Optional[str] = None
        return self.profile

    def execute_action(self, action: BrowserAction) -> BrowserObservation:
        if not self.is_active:
            self.start_session()

        if action.action_type == BrowserActionType.NAVIGATE:
            self.current_url = action.url or "about:blank"
            self.page_title = f"Page: {self.current_url.split('/')[-1] or 'Home'}"
            self.history.append(self.current_url)

        elif action.action_type == BrowserActionType.CLICK:
            if action.target_selector:
                self.dom_state[f"clicked_{action.target_selector}"] = "true"

        elif action.action_type == BrowserActionType.TYPE_TEXT:
            if action.target_selector and action.payload_text:
                self.dom_state[f"input_{action.target_selector}"] = action.payload_text

        return self.get_current_observation()

    def get_current_observation(self) -> BrowserObservation:
        dom_snippet = (
            self.custom_dom_snippet
            if self.custom_dom_snippet is not None
            else (
                f"<html><head><title>{self.page_title}</title></head>"
                f"<body><main url='{self.current_url}' state='{len(self.dom_state)} items'/></body></html>"
            )
        )
        return BrowserObservation(
            current_url=self.current_url,
            page_title=self.page_title,
            dom_snippet=dom_snippet,
            status_code=200,
            screenshot_id=f"snap_{len(self.history)}",
            captured_at=utc_now(),
        )

    def close_session(self) -> None:
        self.is_active = False
        self.dom_state.clear()
