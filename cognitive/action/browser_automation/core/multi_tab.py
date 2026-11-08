"""Multi-tab tracking and management for browser automation sessions."""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TabInfo(BaseModel):
    tab_id: str = Field(default_factory=lambda: f"tab_{uuid.uuid4().hex[:6]}")
    url: str = "about:blank"
    title: str = "New Tab"
    is_active: bool = False
    opened_at: datetime = Field(default_factory=utc_now)


class TabManager:
    """Manages active browser tabs and supports multi-tab switching during automation and human takeover."""

    def __init__(self, initial_url: str = "about:blank", initial_title: str = "New Tab"):
        self._lock = threading.Lock()
        first_tab = TabInfo(url=initial_url, title=initial_title, is_active=True)
        self._tabs: Dict[str, TabInfo] = {first_tab.tab_id: first_tab}
        self._active_tab_id: str = first_tab.tab_id

    def list_tabs(self) -> List[TabInfo]:
        with self._lock:
            return list(self._tabs.values())

    def get_active_tab(self) -> TabInfo:
        with self._lock:
            tab = self._tabs.get(self._active_tab_id)
            if not tab:
                # Fallback to first available
                tab = next(iter(self._tabs.values()))
                self._active_tab_id = tab.tab_id
                tab.is_active = True
            return tab

    def open_tab(self, url: str = "about:blank", title: str = "New Tab", set_active: bool = True) -> TabInfo:
        with self._lock:
            tab = TabInfo(url=url, title=title, is_active=set_active)
            if set_active:
                for t in self._tabs.values():
                    t.is_active = False
                self._active_tab_id = tab.tab_id
            self._tabs[tab.tab_id] = tab
            return tab

    def switch_tab(self, tab_id: str) -> TabInfo:
        with self._lock:
            if tab_id not in self._tabs:
                raise ValueError(f"Tab '{tab_id}' does not exist.")
            for t in self._tabs.values():
                t.is_active = (t.tab_id == tab_id)
            self._active_tab_id = tab_id
            return self._tabs[tab_id]

    def update_tab(self, tab_id: str, url: Optional[str] = None, title: Optional[str] = None) -> TabInfo:
        with self._lock:
            tab = self._tabs.get(tab_id)
            if not tab:
                raise ValueError(f"Tab '{tab_id}' does not exist.")
            if url is not None:
                tab.url = url
            if title is not None:
                tab.title = title
            return tab

    def close_tab(self, tab_id: str) -> bool:
        with self._lock:
            if tab_id not in self._tabs:
                return False
            if len(self._tabs) <= 1:
                # Do not close the last tab, reset to blank
                last_tab = self._tabs[tab_id]
                last_tab.url = "about:blank"
                last_tab.title = "New Tab"
                return True

            del self._tabs[tab_id]
            if self._active_tab_id == tab_id:
                # Activate another tab
                next_tab = next(iter(self._tabs.values()))
                next_tab.is_active = True
                self._active_tab_id = next_tab.tab_id
            return True
