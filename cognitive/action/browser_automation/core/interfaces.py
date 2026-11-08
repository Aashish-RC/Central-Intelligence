"""Abstract interfaces for Pheonix Browser Automation components."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from .models import (
    ActionRiskLevel,
    BrowserAction,
    BrowserObservation,
    BrowserSessionProfile,
    BrowserTaskReport,
)


class BaseActionClassifier(ABC):
    """Interface for classifying browser actions into safe, moderate, or consequential."""

    @abstractmethod
    def classify_action(
        self, action: BrowserAction, current_url: Optional[str] = None
    ) -> tuple[ActionRiskLevel, Optional[str]]:
        """Returns (ActionRiskLevel, consequential_reason)."""
        pass


class BaseConfirmationGate(ABC):
    """Interface for intercepting consequential actions and gating execution on confirmation."""

    @abstractmethod
    def evaluate_and_gate(
        self, action: BrowserAction, current_url: Optional[str] = None
    ) -> bool:
        """Returns True if action is permitted to proceed immediately, False if confirmation is required."""
        pass

    @abstractmethod
    def approve_action(self, action_id: str) -> None:
        pass

    @abstractmethod
    def reject_action(self, action_id: str, reason: str = "User rejected action") -> None:
        pass

    @abstractmethod
    def get_pending_actions(self) -> List[BrowserAction]:
        pass


class BaseBrowserSessionRunner(ABC):
    """Interface for managing the headless browser session and DOM actions."""

    @abstractmethod
    def start_session(self, profile: Optional[BrowserSessionProfile] = None) -> BrowserSessionProfile:
        pass

    @abstractmethod
    def execute_action(self, action: BrowserAction) -> BrowserObservation:
        pass

    @abstractmethod
    def get_current_observation(self) -> BrowserObservation:
        pass

    @abstractmethod
    def close_session(self) -> None:
        pass


class BaseBrowserAgent(ABC):
    """Interface for executing high-level browser tasks."""

    @abstractmethod
    def run_task(
        self,
        task_id: str,
        goal: str,
        planned_actions: List[BrowserAction],
        auto_approve_consequential: bool = False,
    ) -> BrowserTaskReport:
        pass
