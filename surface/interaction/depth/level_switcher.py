"""Depth Level Switcher & Transparency Panel (L18 Interaction - Tasks 18.09, 18.10, 18.11).

Provides Guided / Standard / Pro interaction mode switching, ubiquitous model
selection, and full transparency inspection panels (sources, memories used, token costs).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DepthLevel(str, Enum):
    GUIDED = "guided"
    STANDARD = "standard"
    PRO = "pro"


@dataclass
class TransparencyPanelData:
    """Inspector metrics surfaced in the UI transparency panel."""
    sources_used: List[Dict[str, Any]] = field(default_factory=list)
    memories_recalled: List[Dict[str, Any]] = field(default_factory=list)
    tokens_prompt: int = 0
    tokens_completion: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: float = 0.0
    reasoning_traces_visible: bool = False


class DepthLevelSwitcher:
    """Controls client interaction depth and exposes the full transparency panel."""

    def __init__(
        self,
        initial_level: DepthLevel = DepthLevel.STANDARD,
        initial_model: str = "claude-3-7-sonnet",
    ) -> None:
        self.current_level = initial_level
        self.selected_model = initial_model
        self._panel = TransparencyPanelData()

    def set_depth_level(self, level: DepthLevel) -> DepthLevel:
        """Switch interaction depth level (Guided, Standard, Pro)."""
        self.current_level = level
        # In Pro mode, reasoning traces and granular internals are visible
        self._panel.reasoning_traces_visible = (level == DepthLevel.PRO)
        logger.info("Switched depth level to %s", level.value)
        return self.current_level

    def select_model(self, model_id: str) -> str:
        """Model picker is always accessible regardless of depth level."""
        self.selected_model = model_id
        logger.info("Selected model: %s", model_id)
        return self.selected_model

    def record_turn_provenance(
        self,
        sources: List[Dict[str, Any]],
        memories: List[Dict[str, Any]],
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        latency_ms: float,
    ) -> TransparencyPanelData:
        """Update transparency panel with live turn execution telemetry."""
        self._panel.sources_used = list(sources)
        self._panel.memories_recalled = list(memories)
        self._panel.tokens_prompt = prompt_tokens
        self._panel.tokens_completion = completion_tokens
        self._panel.estimated_cost_usd = cost_usd
        self._panel.latency_ms = latency_ms
        return self._panel

    def get_transparency_panel(self) -> TransparencyPanelData:
        """Retrieve current transparency inspection data."""
        return self._panel

    def get_system_prompt_modifier(self) -> str:
        """Provide system prompt directives tailored to active depth level."""
        if self.current_level == DepthLevel.GUIDED:
            return "Provide beginner-friendly, step-by-step guidance. Avoid dense technical jargon."
        elif self.current_level == DepthLevel.PRO:
            return "Provide concise, expert-level technical answers with full architectural precision, code diffs, and exact algorithms."
        return "Provide balanced, clear, and comprehensive assistance."

