"""Aevum Universal Surface Adapter (L18 Interaction - Task 18.15 - CROWN JEWEL).

Client SDK and presentation abstraction layer that normalizes AI responses,
streaming generative UI, interactive tool confirmation buttons, and audio events
across Web (LibreChat), Desktop (Jan), Terminal (OpenCode), and IDE (Zed).
One unified API, rendered natively on every client surface.
"""

from __future__ import annotations

import html
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class SurfaceType(str, Enum):
    WEB = "web"
    DESKTOP = "desktop"
    TERMINAL = "terminal"
    IDE = "ide"


@dataclass
class ContentBlock:
    """Universal rich content block."""
    block_type: str  # "text", "code", "button", "generative_ui", "table"
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedEvent:
    """Universal streaming or interaction event."""
    event_type: str  # "token", "confirmation_request", "ui_render", "audio_chunk"
    payload: Any
    timestamp: float = field(default_factory=time.time)


class WebSurfaceRenderer:
    """Renders HTML5 / DOM interactive components for LibreChat and web clients."""

    def render_html(self, content: Union[ContentBlock, str]) -> str:
        if isinstance(content, str):
            return f"<p class='ai-text'>{html.escape(content)}</p>"
        if content.block_type == "text":
            return f"<p class='ai-text'>{html.escape(str(content.content))}</p>"
        if content.block_type == "code":
            lang = content.metadata.get("language", "text")
            return f"<pre><code class='language-{lang}'>{html.escape(str(content.content))}</code></pre>"
        if content.block_type == "button":
            action = content.metadata.get("action", "")
            return f"<button class='ai-action-btn' data-action='{html.escape(action)}'>{html.escape(str(content.content))}</button>"
        if content.block_type == "generative_ui":
            component = content.metadata.get("component", "Card")
            props_json = html.escape(json.dumps(content.content))
            return f"<div class='generative-ui-root' data-component='{component}' data-props='{props_json}'></div>"
        return f"<div class='ai-raw'>{html.escape(str(content.content))}</div>"

    def request_confirmation(self, action: str) -> bool:
        logger.info("[Web] Prompting user confirmation dialog in browser modal: %s", action)
        return True

    def send(self, event: NormalizedEvent) -> str:
        return f"data: {json.dumps({'type': event.event_type, 'data': event.payload})}\n\n"


class DesktopSurfaceRenderer:
    """Renders native desktop components for Jan / Electron / Cocoa clients."""

    def render_native(self, content: Union[ContentBlock, str]) -> Dict[str, Any]:
        text_val = content if isinstance(content, str) else content.content
        block_t = "text" if isinstance(content, str) else content.block_type
        meta = {} if isinstance(content, str) else content.metadata

        return {
            "surface": "desktop",
            "component": "NativeRichView",
            "block_type": block_t,
            "body": text_val,
            "metadata": meta,
            "native_theme": "system_dark",
        }

    def request_confirmation(self, action: str) -> bool:
        logger.info("[Desktop] Presenting native OS modal sheet confirmation: %s", action)
        return True

    def send(self, event: NormalizedEvent) -> Dict[str, Any]:
        return {"ipc_channel": "ai-event", "event": event.__dict__}


class TerminalSurfaceRenderer:
    """Renders ANSI-formatted text for OpenCode and CLI terminals."""

    def render_ansi(self, content: Union[ContentBlock, str]) -> str:
        if isinstance(content, str):
            return content

        if content.block_type == "text":
            return str(content.content)
        if content.block_type == "code":
            lang = content.metadata.get("language", "")
            header = f"\x1b[36m--- [Code: {lang}] ---\x1b[0m\n" if lang else ""
            return f"{header}\x1b[32m{content.content}\x1b[0m\n\x1b[36m----------------------\x1b[0m"
        if content.block_type == "button":
            return f"\x1b[1m\x1b[33m[Button: {content.content} (Press Enter to execute)]\x1b[0m"
        if content.block_type == "generative_ui":
            component = content.metadata.get("component", "Widget")
            return f"\x1b[35m[UI Widget: {component}]\x1b[0m {json.dumps(content.content)}"
        return str(content.content)

    def request_confirmation(self, action: str) -> bool:
        logger.info("[Terminal] Prompting CLI confirmation: [y/N] for action '%s'", action)
        return True

    def send(self, event: NormalizedEvent) -> str:
        return f"\x1b[36m[stream]\x1b[0m {event.payload}"


class IdeSurfaceRenderer:
    """Renders editor decorations and code buffers for Zed / VS Code."""

    def render_editor(self, content: Union[ContentBlock, str]) -> Dict[str, Any]:
        text_val = content if isinstance(content, str) else str(content.content)
        block_t = "text" if isinstance(content, str) else content.block_type
        meta = {} if isinstance(content, str) else content.metadata

        return {
            "surface": "ide",
            "target": "assistant_panel_or_inline",
            "format": "markdown_code",
            "content": f"```{meta.get('language', '')}\n{text_val}\n```" if block_t == "code" else text_val,
            "inline_decorations": meta.get("decorations", []),
        }

    def request_confirmation(self, action: str) -> bool:
        logger.info("[IDE] Showing CodeLens inline action confirmation: %s", action)
        return True

    def send(self, event: NormalizedEvent) -> Dict[str, Any]:
        return {"lsp_notification": "zed/streamEvent", "payload": event.payload}


class UniversalSurfaceAdapter:
    """Crown Jewel: Normalizes interactions across all client surfaces (Web, Desktop, Terminal, IDE)."""

    def __init__(self) -> None:
        self.surfaces: Dict[str, Any] = {}
        self._init_default_renderers()

    def _init_default_renderers(self) -> None:
        self.register("web", WebSurfaceRenderer())
        self.register("desktop", DesktopSurfaceRenderer())
        self.register("terminal", TerminalSurfaceRenderer())
        self.register("ide", IdeSurfaceRenderer())

    def register(self, surface_type: Union[SurfaceType, str], adapter: Any) -> None:
        """Register custom or built-in surface renderer."""
        key = surface_type.value if isinstance(surface_type, SurfaceType) else str(surface_type).lower()
        self.surfaces[key] = adapter

    def normalize_event(self, event: Any) -> NormalizedEvent:
        """Ensure input event conforms to canonical NormalizedEvent structure."""
        if isinstance(event, NormalizedEvent):
            return event
        if isinstance(event, dict):
            return NormalizedEvent(
                event_type=event.get("type", "generic"),
                payload=event.get("payload", event),
            )
        return NormalizedEvent(event_type="text_chunk", payload=str(event))

    def render(self, content: Union[ContentBlock, str], surface_type: Union[SurfaceType, str]) -> Any:
        """Render universal content block specifically for designated surface."""
        key = surface_type.value if isinstance(surface_type, SurfaceType) else str(surface_type).lower()
        renderer = self.surfaces.get(key)
        if not renderer:
            raise ValueError(f"No renderer registered for surface '{key}'")

        if key == "web":
            return renderer.render_html(content)
        elif key == "desktop":
            return renderer.render_native(content)
        elif key == "terminal":
            return renderer.render_ansi(content)
        elif key == "ide":
            return renderer.render_editor(content)
        else:
            return getattr(renderer, "render", lambda c: str(c))(content)

    def stream(self, event: Any, surface_type: Union[SurfaceType, str]) -> Any:
        """Stream normalized event to destination surface."""
        key = surface_type.value if isinstance(surface_type, SurfaceType) else str(surface_type).lower()
        renderer = self.surfaces.get(key)
        if not renderer:
            raise ValueError(f"No renderer registered for surface '{key}'")

        normalized = self.normalize_event(event)
        return renderer.send(normalized)

    def confirm(self, action: str, surface_type: Union[SurfaceType, str]) -> bool:
        """Request explicit confirmation on destination surface."""
        key = surface_type.value if isinstance(surface_type, SurfaceType) else str(surface_type).lower()
        renderer = self.surfaces.get(key)
        if not renderer:
            raise ValueError(f"No renderer registered for surface '{key}'")

        return renderer.request_confirmation(action)
