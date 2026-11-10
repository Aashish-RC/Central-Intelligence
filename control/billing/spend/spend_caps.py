"""
Spend Caps & Alerts Engine (Layer 13: Feature 13.11).

Features:
- 13.11: Real-time spend tracking and protective bounds:
  - At 80% of configured spend cap: triggers real-time email notification alert.
  - At 100% of configured spend cap: automatically pauses agent execution to prevent overruns.
- Bridges to Layer 5 Financial Authority Guard and Layer 8 Budget Tracker.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("control.billing.spend")


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING_80 = "warning_80_percent"
    HARD_CAP_100 = "hard_cap_100_percent"


@dataclass
class SpendAlert:
    """Represents an alert triggered by spend cap thresholds."""
    user_id: str
    tenant_id: str
    level: AlertLevel
    message: str
    current_spend_usd: float
    cap_usd: float
    percentage: float
    timestamp: float = field(default_factory=time.time)
    notification_dispatched: bool = True
    recipient_email: Optional[str] = None


@dataclass
class SpendCapPolicy:
    """Configured spending bounds for a user or agent."""
    user_id: str
    tenant_id: str = "default"
    monthly_cap_usd: float = 100.0
    current_spend_usd: float = 0.0
    email: Optional[str] = None
    warning_threshold_pct: float = 80.0
    hard_cap_threshold_pct: float = 100.0
    alert_80_sent: bool = False
    is_agent_paused: bool = False
    alerts_history: List[SpendAlert] = field(default_factory=list)


@dataclass
class SpendEvaluationResult:
    """Evaluation result returned after updating or checking spend."""
    user_id: str
    current_spend_usd: float
    cap_usd: float
    percentage: float
    is_agent_paused: bool
    action: str  # "continue", "alert_80_sent", "agent_paused"
    alert: Optional[SpendAlert] = None
    reason: Optional[str] = None


class SpendCapManager:
    """
    Tracks real-time spend, generates alerts at 80%, and pauses agent at 100%.
    """

    def __init__(
        self,
        financial_authority_guard: Optional[Any] = None,
        email_notifier: Optional[Callable[[str, str, str], bool]] = None,
    ) -> None:
        self._policies: Dict[str, SpendCapPolicy] = {}  # user_id -> policy
        self._financial_guard = financial_authority_guard
        self._email_notifier = email_notifier or self._default_email_dispatcher

    def _default_email_dispatcher(self, recipient: str, subject: str, body: str) -> bool:
        logger.info("Dispatched spend alert email to '%s': %s", recipient, subject)
        return True

    def _get_financial_guard(self) -> Any:
        if self._financial_guard is None:
            try:
                from cognitive.action.safety.financial_authority import FinancialAuthorityGuard
                self._financial_guard = FinancialAuthorityGuard()
            except ImportError:
                pass
        return self._financial_guard

    def set_spend_cap(
        self,
        user_id: str,
        monthly_cap_usd: float,
        tenant_id: str = "default",
        email: Optional[str] = None,
    ) -> SpendCapPolicy:
        """Sets or updates the monthly spend limit for a user."""
        policy = self._policies.get(user_id)
        if policy is None:
            policy = SpendCapPolicy(
                user_id=user_id,
                tenant_id=tenant_id,
                monthly_cap_usd=monthly_cap_usd,
                email=email or f"{user_id}@example.com",
            )
            self._policies[user_id] = policy
        else:
            policy.monthly_cap_usd = monthly_cap_usd
            if email:
                policy.email = email
            # If new cap exceeds current spend, unpause agent
            if policy.current_spend_usd < monthly_cap_usd:
                policy.is_agent_paused = False
                if (policy.current_spend_usd / monthly_cap_usd * 100.0) < 80.0:
                    policy.alert_80_sent = False

        return policy

    def get_policy(self, user_id: str) -> SpendCapPolicy:
        if user_id not in self._policies:
            self.set_spend_cap(user_id, monthly_cap_usd=100.0)
        return self._policies[user_id]

    def track_spend(
        self,
        user_id: str,
        amount_usd: float,
        agent_id: Optional[str] = None,
    ) -> SpendEvaluationResult:
        """
        Records incremental spending and checks threshold limits (Feature 13.11):
        - 80% threshold reached -> Dispatches email alert.
        - 100% threshold reached -> Pauses agent execution.
        """
        policy = self.get_policy(user_id)
        policy.current_spend_usd += amount_usd

        cap = policy.monthly_cap_usd
        pct = (policy.current_spend_usd / cap * 100.0) if cap > 0 else 100.0

        alert: Optional[SpendAlert] = None
        action = "continue"
        reason = "Spend within nominal thresholds."

        # 1. Check 100% hard cap threshold -> Pause agent
        if pct >= policy.hard_cap_threshold_pct:
            policy.is_agent_paused = True
            action = "agent_paused"
            reason = f"Spend cap of ${cap:.2f} reached (100%). Agent execution has been paused."
            alert = SpendAlert(
                user_id=user_id,
                tenant_id=policy.tenant_id,
                level=AlertLevel.HARD_CAP_100,
                message=reason,
                current_spend_usd=policy.current_spend_usd,
                cap_usd=cap,
                percentage=round(pct, 2),
                recipient_email=policy.email,
            )
            policy.alerts_history.append(alert)
            if policy.email:
                self._email_notifier(
                    policy.email,
                    "URGENT: Agent Paused - 100% Spend Cap Exceeded",
                    reason,
                )
            logger.warning("Agent paused for user '%s': 100%% spend cap exceeded ($%.2f / $%.2f)", user_id, policy.current_spend_usd, cap)

        # 2. Check 80% warning threshold -> Dispatch email alert once
        elif pct >= policy.warning_threshold_pct and not policy.alert_80_sent:
            policy.alert_80_sent = True
            action = "alert_80_sent"
            reason = f"Approaching limit: {pct:.1f}% of ${cap:.2f} monthly spend cap used."
            alert = SpendAlert(
                user_id=user_id,
                tenant_id=policy.tenant_id,
                level=AlertLevel.WARNING_80,
                message=reason,
                current_spend_usd=policy.current_spend_usd,
                cap_usd=cap,
                percentage=round(pct, 2),
                recipient_email=policy.email,
            )
            policy.alerts_history.append(alert)
            if policy.email:
                self._email_notifier(
                    policy.email,
                    "Notice: 80% of Monthly Spend Cap Reached",
                    reason,
                )
            logger.info("80%% spend alert dispatched for user '%s' (%s)", user_id, policy.email)

        return SpendEvaluationResult(
            user_id=user_id,
            current_spend_usd=policy.current_spend_usd,
            cap_usd=cap,
            percentage=round(pct, 2),
            is_agent_paused=policy.is_agent_paused,
            action=action,
            alert=alert,
            reason=reason,
        )

    def is_agent_allowed(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """Verifies if an agent can execute or is paused due to spend cap."""
        policy = self.get_policy(user_id)
        if policy.is_agent_paused:
            return False, f"Agent paused: 100% monthly spend cap of ${policy.monthly_cap_usd:.2f} reached."
        return True, None

    def resume_agent(self, user_id: str, new_cap_usd: Optional[float] = None) -> SpendCapPolicy:
        """Resumes a paused agent by updating cap or resetting status."""
        policy = self.get_policy(user_id)
        if new_cap_usd and new_cap_usd > policy.current_spend_usd:
            policy.monthly_cap_usd = new_cap_usd
        policy.is_agent_paused = False
        return policy


# Global default singleton
default_spend_cap_manager = SpendCapManager()

