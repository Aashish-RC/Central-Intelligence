"""
Situational Context Probe (Layer 1: Perception, Task 1.9; Feature 1.47).

Probes real-time ambient environment: current date, time, timezone, system locale,
device type, and real-time user activity. Supplies grounded context to Layer 9
Context Engineering Situational Injector.
"""

from __future__ import annotations

import locale
import logging
import os
import platform
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import zoneinfo

logger = logging.getLogger("cognitive.perception.situational.probe")


@dataclass
class ProbeResult:
    """Environment telemetry result probed from the user's host system."""
    date: str
    time: str
    tz: str
    locale: str
    device: str
    activity: str
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Acceptance: Returns {date, time, tz, locale, device, activity}.
        """
        return {
            "date": self.date,
            "time": self.time,
            "tz": self.tz,
            "locale": self.locale,
            "device": self.device,
            "activity": self.activity,
        }


class SituationalContextProbe:
    """
    Situational Context Probe discovering ambient runtime context (Task 1.9).
    """

    def __init__(
        self,
        default_tz: Optional[str] = None,
        screen_adapter: Optional[Any] = None,
    ) -> None:
        self.default_tz = default_tz
        self.screen_adapter = screen_adapter

    def detect_device_type(self) -> str:
        """Determines device form factor from system metadata."""
        sys_name = platform.system().lower()
        node = platform.node().lower()
        # Common heuristics for laptop vs desktop vs container
        if "docker" in node or os.path.exists("/.dockerenv"):
            return "container"
        return "desktop" if sys_name in ("windows", "darwin", "linux") else "mobile"

    def detect_timezone(self) -> str:
        """Identifies local timezone identifier."""
        if self.default_tz:
            return self.default_tz
        try:
            return time.tzname[0] or "UTC"
        except Exception:
            return "UTC"

    def detect_locale(self) -> str:
        """Determines host locale setting."""
        try:
            loc = locale.getlocale()[0]
            if loc:
                return loc.replace("_", "-")
        except Exception:
            pass
        return "en-US"

    def infer_activity(self, active_window: Optional[str] = None) -> str:
        """
        Infers current user activity from active window title, screen context, or default state.
        """
        if not active_window and self.screen_adapter:
            try:
                frames = self.screen_adapter.what_was_on_screen(seconds_ago=10.0)
                if frames:
                    active_window = frames[0].window_title or frames[0].app_name
            except Exception:
                pass

        if active_window:
            lower = active_window.lower()
            if any(k in lower for k in ("slack", "teams", "discord", "zoom", "chat")):
                return "collaborating"
            if any(k in lower for k in ("chrome", "firefox", "edge", "safari", "github", "http://", "https://")):
                return "browsing"
            if any(k in lower for k in ("terminal", "powershell", "bash", "cmd.exe", "zsh", "alacritty", "iterm")):
                return "terminal operations"
            if any(k in lower for k in ("vscode", "visual studio", "pycharm", "intellij", "sublime", "vim", "cursor", "zed", ".py", ".ts", ".js", ".rs", ".go")):
                return "coding"

        return "active user interaction"


    def probe(
        self,
        current_time: Optional[datetime] = None,
        active_window: Optional[str] = None,
    ) -> ProbeResult:
        """
        Acceptance: Probes environment and returns {date, time, tz, locale, device, activity}.
        """
        dt = current_time or datetime.now(timezone.utc)
        tz_str = self.detect_timezone()

        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%I:%M:%S %p").lstrip("0")
        locale_str = self.detect_locale()
        device_str = self.detect_device_type()
        activity_str = self.infer_activity(active_window=active_window)

        return ProbeResult(
            date=date_str,
            time=time_str,
            tz=tz_str,
            locale=locale_str,
            device=device_str,
            activity=activity_str,
            extra={"platform": platform.system().lower()},
        )

    def supply_to_l9(
        self,
        active_workspace: Optional[str] = None,
        active_document: Optional[str] = None,
        active_window: Optional[str] = None,
    ) -> Any:
        """
        Supplies probed context directly to Layer 9 SituationalInjector.
        """
        from control.context.situational.injector import SituationalContext, SituationalInjector

        res = self.probe(active_window=active_window)
        return SituationalInjector.capture(
            tz_name=res.tz,
            locale=res.locale,
            device_type=res.device,
            platform=platform.system().lower(),
            active_workspace=active_workspace,
            active_document=active_document,
            user_activity=res.activity,
        )


# Global default instance
default_context_probe = SituationalContextProbe()

