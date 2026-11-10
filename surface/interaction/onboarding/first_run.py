"""First-Run Onboarding Wizard (L18 Interaction - Task 18.42).

Walks users through initial deployment: telemetry opt-ins, default AI model selection,
and secure entry of provider credentials.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OnboardingStep(str, Enum):
    WELCOME = "welcome"
    PROVIDER_SELECTION = "provider_selection"
    API_KEY_SETUP = "api_key_setup"
    PREFERENCES = "preferences"
    COMPLETED = "completed"


@dataclass
class OnboardingState:
    """Snapshot of onboarding progress."""
    current_step: OnboardingStep = OnboardingStep.WELCOME
    is_completed: bool = False
    configured_provider: Optional[str] = None
    has_api_key: bool = False
    telemetry_opt_in: bool = False


class FirstRunWizard:
    """Manages multi-step initial onboarding wizard."""

    def __init__(self) -> None:
        self.state = OnboardingState()
        self._credentials: Dict[str, str] = {}

    def next_step(self) -> OnboardingStep:
        """Advance wizard step."""
        order = [
            OnboardingStep.WELCOME,
            OnboardingStep.PROVIDER_SELECTION,
            OnboardingStep.API_KEY_SETUP,
            OnboardingStep.PREFERENCES,
            OnboardingStep.COMPLETED,
        ]
        curr_idx = order.index(self.state.current_step)
        if curr_idx < len(order) - 1:
            self.state.current_step = order[curr_idx + 1]
            if self.state.current_step == OnboardingStep.COMPLETED:
                self.state.is_completed = True
        return self.state.current_step

    def configure_provider_key(self, provider: str, api_key: str) -> bool:
        """Securely register provider API key during onboarding."""
        if not api_key or len(api_key.strip()) < 8:
            raise ValueError("Invalid API key format")

        self.state.configured_provider = provider
        self.state.has_api_key = True
        self._credentials[provider] = api_key
        logger.info("Configured provider credentials for %s", provider)
        return True

    def get_credential(self, provider: str) -> Optional[str]:
        return self._credentials.get(provider)

