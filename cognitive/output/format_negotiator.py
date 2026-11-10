"""Output Format Negotiator (Feature 6.35)

Selects and tailors output formats based on the client target surface:
web vs mobile vs CLI vs email vs voice.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TargetSurface(str, Enum):
    WEB = "web"
    MOBILE = "mobile"
    CLI = "cli"
    EMAIL = "email"
    VOICE = "voice"


@dataclass
class ContentPayload:
    """Unified semantic content structure before surface formatting."""
    title: str
    body: str
    summary: Optional[str] = None
    bullet_points: List[str] = field(default_factory=list)
    code_snippets: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NegotiatedOutput:
    """Surface-adapted rendered output."""
    surface: TargetSurface
    format_type: str  # e.g., 'ansi_text', 'html', 'mobile_card_json', 'email_mime'
    formatted_content: str
    is_interactive: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


class OutputFormatNegotiator:
    """Negotiates presentation format optimized for client constraints."""

    def negotiate(
        self,
        content: ContentPayload,
        surface: TargetSurface | str,
        max_width: int = 80,
    ) -> NegotiatedOutput:
        """Render content payload tailored to the specified surface."""
        target = TargetSurface(surface) if isinstance(surface, str) else surface

        if target == TargetSurface.CLI:
            return self._format_cli(content, max_width)
        elif target == TargetSurface.MOBILE:
            return self._format_mobile(content)
        elif target == TargetSurface.WEB:
            return self._format_web(content)
        elif target == TargetSurface.EMAIL:
            return self._format_email(content)
        elif target == TargetSurface.VOICE:
            return self._format_voice(content)
        else:
            return self._format_web(content)

    def _format_cli(self, content: ContentPayload, max_width: int) -> NegotiatedOutput:
        lines: List[str] = []
        # Bold/cyan header
        border = "=" * min(len(content.title) + 4, max_width)
        lines.append(f"\033[1;36m{border}\033[0m")
        lines.append(f"\033[1;36m  {content.title}  \033[0m")
        lines.append(f"\033[1;36m{border}\033[0m")
        lines.append("")

        if content.summary:
            lines.append(f"\033[3mSummary: {content.summary}\033[0m")
            lines.append("")

        lines.append(content.body)

        if content.bullet_points:
            lines.append("")
            for pt in content.bullet_points:
                lines.append(f"  * {pt}")

        for snippet in content.code_snippets:
            lang = snippet.get("language", "")
            code = snippet.get("code", "")
            lines.append("")
            lines.append(f"--- [Code: {lang}] ---")
            lines.append(code)
            lines.append("---------------------")

        return NegotiatedOutput(
            surface=TargetSurface.CLI,
            format_type="ansi_text",
            formatted_content="\n".join(lines),
            is_interactive=False,
            metadata={"terminal_width": max_width},
        )

    def _format_mobile(self, content: ContentPayload) -> NegotiatedOutput:
        # Compact, high-signal, viewport-constrained representation
        summary = content.summary or (content.body[:140] + "..." if len(content.body) > 140 else content.body)
        sections: List[str] = [f"### 📱 {content.title}"]
        sections.append(f"> **Quick Take**: {summary}")

        if content.bullet_points:
            sections.append("**Highlights:**")
            for pt in content.bullet_points[:3]:  # Top 3 items for mobile viewport
                sections.append(f"• {pt}")

        return NegotiatedOutput(
            surface=TargetSurface.MOBILE,
            format_type="mobile_markdown",
            formatted_content="\n\n".join(sections),
            is_interactive=True,
            metadata={"compact_mode": True, "touch_optimized": True},
        )

    def _format_web(self, content: ContentPayload) -> NegotiatedOutput:
        # Full rich HTML / Markdown with interactive widgets
        parts: List[str] = [f"# {content.title}\n"]
        if content.summary:
            parts.append(f"> {content.summary}\n")
        parts.append(f"{content.body}\n")

        if content.bullet_points:
            parts.append("### Key Takeaways\n")
            for pt in content.bullet_points:
                parts.append(f"- {pt}")
            parts.append("")

        for snippet in content.code_snippets:
            lang = snippet.get("language", "text")
            parts.append(f"```{lang}\n{snippet.get('code', '')}\n```\n")

        return NegotiatedOutput(
            surface=TargetSurface.WEB,
            format_type="rich_markdown",
            formatted_content="\n".join(parts),
            is_interactive=True,
            metadata={"supports_react": True, "supports_canvas": True},
        )

    def _format_email(self, content: ContentPayload) -> NegotiatedOutput:
        # Clean HTML email markup with inline CSS
        html = [
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; color: #1e293b;">',
            f'  <h1 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">{content.title}</h1>',
        ]
        if content.summary:
            html.append(f'  <p style="background: #f8fafc; padding: 12px; border-left: 4px solid #3b82f6; font-style: italic;">{content.summary}</p>')
        html.append(f'  <p>{content.body}</p>')

        if content.bullet_points:
            html.append('  <ul>')
            for pt in content.bullet_points:
                html.append(f'    <li>{pt}</li>')
            html.append('  </ul>')

        html.append('</div>')

        return NegotiatedOutput(
            surface=TargetSurface.EMAIL,
            format_type="email_html",
            formatted_content="\n".join(html),
            is_interactive=False,
            metadata={"mime_type": "text/html"},
        )

    def _format_voice(self, content: ContentPayload) -> NegotiatedOutput:
        # Conversational speech-ready text with SSML hints
        spoken_text = f"{content.title}. "
        if content.summary:
            spoken_text += f"{content.summary}. "
        else:
            spoken_text += f"{content.body}. "

        if content.bullet_points:
            spoken_text += "Here are the main points: " + ", ".join(content.bullet_points) + "."

        return NegotiatedOutput(
            surface=TargetSurface.VOICE,
            format_type="ssml_text",
            formatted_content=f"<speak>{spoken_text}</speak>",
            is_interactive=False,
            metadata={"speech_rate": "1.0"},
        )

