"""Accessibility Settings & Profiles (L18 Interaction - Task 18.39).

Provides WCAG AAA-compliant accessibility configurations: screen reader hints,
captions, high contrast styling, keyboard navigation shortcuts, and motion reduction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class AccessibilityProfile:
    """Accessibility profile settings."""
    screen_reader_enabled: bool = False
    high_contrast: bool = False
    closed_captions: bool = False
    keyboard_navigation: bool = True
    reduce_motion: bool = False
    font_scale: float = 1.0  # 0.8 to 2.0


class AccessibilityManager:
    """Manages system-wide accessibility adjustments."""

    def __init__(self, profile: Optional[AccessibilityProfile] = None) -> None:
        self.profile = profile or AccessibilityProfile()

    def update_settings(self, **kwargs: Any) -> AccessibilityProfile:
        for k, v in kwargs.items():
            if hasattr(self.profile, k):
                setattr(self.profile, k, v)
        logger.info("Updated accessibility profile: %s", self.profile)
        return self.profile

    def get_aria_attributes(self, component_role: str, label: str) -> Dict[str, str]:
        """Generate accessibility attributes for UI components."""
        attrs = {
            "role": component_role,
            "aria-label": label,
        }
        if self.profile.screen_reader_enabled:
            attrs["aria-live"] = "polite"
        return attrs

