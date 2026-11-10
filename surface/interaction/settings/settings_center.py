"""Unified Settings Center (L18 Interaction - Task 18.38).

Single entrypoint control plane that aggregates Accessibility, Localization,
First-Run Wizard state, and Provider API Key credentials in one place.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from surface.interaction.accessibility.accessibility import (
    AccessibilityManager,
    AccessibilityProfile,
)
from surface.interaction.localization.localization import (
    LocalizationManager,
    LocaleProfile,
)
from surface.interaction.onboarding.first_run import (
    FirstRunWizard,
    OnboardingState,
)

logger = logging.getLogger(__name__)


@dataclass
class UnifiedSettingsSnapshot:
    """Consolidated state of user settings."""
    accessibility: AccessibilityProfile
    locale: LocaleProfile
    onboarding: OnboardingState
    api_keys_configured: Dict[str, bool] = field(default_factory=dict)


class SettingsCenter:
    """Unified Settings Manager coordinating all client preferences."""

    def __init__(self) -> None:
        self.accessibility = AccessibilityManager()
        self.localization = LocalizationManager()
        self.onboarding = FirstRunWizard()
        self._provider_keys: Dict[str, str] = {}

    def set_provider_key(self, provider: str, api_key: str) -> None:
        """Register provider API key in user configuration."""
        self._provider_keys[provider] = api_key
        self.onboarding.configure_provider_key(provider, api_key)

    def get_provider_key(self, provider: str) -> Optional[str]:
        return self._provider_keys.get(provider)

    def get_settings_snapshot(self) -> UnifiedSettingsSnapshot:
        """Export comprehensive settings snapshot."""
        return UnifiedSettingsSnapshot(
            accessibility=self.accessibility.profile,
            locale=self.localization.locale,
            onboarding=self.onboarding.state,
            api_keys_configured={p: True for p in self._provider_keys},
        )

