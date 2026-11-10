"""Situational Context Injector (Layer 9: Context Engineering, Feature 9.16).

Injects real-time temporal markers, geographic locale, client platform, and
workspace context into system prompt frames.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import zoneinfo
from typing import Any, Dict, Optional


@dataclass
class SituationalContext:
    """Captured runtime environmental context."""
    timestamp_iso: str
    formatted_datetime: str
    timezone_name: str
    locale: str = "en-US"
    device_type: str = "desktop"
    platform: str = "windows"
    active_workspace: Optional[str] = None
    active_document: Optional[str] = None
    user_activity: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SituationalInjector:
    """Captures and formats situational ambient context for model grounding (9.16)."""

    @classmethod
    def capture(
        cls,
        dt: Optional[datetime] = None,
        tz_name: str = "UTC",
        locale: str = "en-US",
        device_type: str = "desktop",
        platform: str = "windows",
        active_workspace: Optional[str] = None,
        active_document: Optional[str] = None,
        user_activity: Optional[str] = None,
    ) -> SituationalContext:
        """Captures structured situational snapshot."""
        if dt is None:
            dt = datetime.now(timezone.utc)

        # Convert to target timezone if possible
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
            dt_localized = dt.astimezone(tz)
        except Exception:
            dt_localized = dt

        timestamp_iso = dt_localized.isoformat()
        # Format human-readable string: "3:45 PM on November 9, 2026"
        # Using %I:%M %p on %B %d, %Y
        time_part = dt_localized.strftime("%I:%M %p").lstrip("0")
        date_part = dt_localized.strftime("%B %d, %Y").replace(" 0", " ")
        formatted = f"{time_part} on {date_part}"

        return SituationalContext(
            timestamp_iso=timestamp_iso,
            formatted_datetime=formatted,
            timezone_name=tz_name,
            locale=locale,
            device_type=device_type,
            platform=platform,
            active_workspace=active_workspace,
            active_document=active_document,
            user_activity=user_activity,
        )

    @classmethod
    def capture_from_probe(
        cls,
        probe: Optional[Any] = None,
        active_workspace: Optional[str] = None,
        active_document: Optional[str] = None,
        active_window: Optional[str] = None,
    ) -> SituationalContext:
        """Captures situational context directly using Layer 1 SituationalContextProbe (Task 1.9)."""
        if probe is None:
            try:
                from cognitive.perception.situational.context_probe import default_context_probe
                probe = default_context_probe
            except ImportError:
                return cls.capture(
                    active_workspace=active_workspace,
                    active_document=active_document,
                )
        return probe.supply_to_l9(
            active_workspace=active_workspace,
            active_document=active_document,
            active_window=active_window,
        )


    @classmethod
    def format_block(cls, ctx: SituationalContext) -> str:
        """Formats the situational context into a structured prompt injection block."""
        lines = [
            f"- Current Time: {ctx.formatted_datetime} ({ctx.timezone_name})",
            f"- ISO Timestamp: {ctx.timestamp_iso}",
            f"- Locale & Language: {ctx.locale}",
            f"- Client Environment: {ctx.platform} ({ctx.device_type})",
        ]
        if ctx.active_workspace:
            lines.append(f"- Active Workspace: {ctx.active_workspace}")
        if ctx.active_document:
            lines.append(f"- Open Document: {ctx.active_document}")
        if ctx.user_activity:
            lines.append(f"- Current User Activity: {ctx.user_activity}")

        return "\n".join(lines)
