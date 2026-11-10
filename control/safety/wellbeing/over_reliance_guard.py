"""
Over-Reliance Guard (Feature 10.55)
Monitors human-AI interaction dynamics for cognitive over-reliance and decision-deferral patterns.
When a user defers autonomous agency to the AI repeatedly (e.g., >= 10 consecutive times),
the guard triggers a wellbeing advisory prompting the user to exercise independent judgment.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

DEFERRAL_PATTERNS = [
    r"(?i)\bwhat\s+should\s+i\s+do\b",
    r"(?i)\b(?:you\s+decide|make\s+the\s+decision\s+for\s+me|decide\s+for\s+me|tell\s+me\s+what\s+to\s+do)\b",
    r"(?i)\b(?:which\s+one\s+should\s+i\s+choose|pick\s+(?:one\s+)?for\s+me|you\s+choose)\b",
    r"(?i)\b(?:should\s+i\s+(?:quit|leave|break\s+up|accept|reject|marry|divorce|buy|sell|move))\b",
    r"(?i)\b(?:make\s+up\s+my\s+mind|choose\s+for\s+me|take\s+the\s+call)\b",
]

AGENCY_ASSERTION_PATTERNS = [
    r"(?i)\bi(?:\s+have)?\s+(?:decided|chosen|prefer|want)\s+to\b",
    r"(?i)\bmy\s+choice\s+is\b",
    r"(?i)\bi\s+will\s+(?:go\s+with|take|do|pick)\b",
    r"(?i)\bi\s+disagree\b",
]

DEFAULT_WELLBEING_WARNING = (
    "Wellbeing Advisory (Over-Reliance Notice): You have deferred decisions to the AI "
    "10 or more times consecutively. While I can offer perspectives and weigh pros and cons, "
    "this choice affects your life and should be made using your own judgment and values."
)


@dataclass
class UserRelianceState:
    user_id: str
    tenant_id: str = "default"
    consecutive_deferrals: int = 0
    total_deferrals: int = 0
    last_deferral_timestamp: Optional[float] = None
    warning_triggered: bool = False
    warning_count: int = 0
    history: List[str] = field(default_factory=list)


class OverRelianceGuard:
    """
    Tracks and mitigates cognitive over-reliance on AI decision-making (Feature 10.55).
    """

    def __init__(self, threshold: int = 10, warning_message: str = DEFAULT_WELLBEING_WARNING):
        self.threshold = threshold
        self.warning_message = warning_message
        self._states: Dict[str, UserRelianceState] = {}
        self._compiled_deferrals = [re.compile(p, re.IGNORECASE) for p in DEFERRAL_PATTERNS]
        self._compiled_assertions = [re.compile(p, re.IGNORECASE) for p in AGENCY_ASSERTION_PATTERNS]

    def _key(self, user_id: str, tenant_id: str = "default") -> str:
        return f"{tenant_id}:{user_id}"

    def get_state(self, user_id: str, tenant_id: str = "default") -> UserRelianceState:
        k = self._key(user_id, tenant_id)
        if k not in self._states:
            self._states[k] = UserRelianceState(user_id=user_id, tenant_id=tenant_id)
        return self._states[k]

    def is_decision_deferral(self, text: str) -> bool:
        """Evaluates whether the user's prompt is deferring decision-making agency to the AI."""
        if not text:
            return False
        return any(pat.search(text) for pat in self._compiled_deferrals)

    def is_agency_assertion(self, text: str) -> bool:
        """Evaluates whether the user is asserting their own independent agency/choice."""
        if not text:
            return False
        return any(pat.search(text) for pat in self._compiled_assertions)

    def evaluate_turn(
        self,
        user_id: str,
        prompt: str,
        tenant_id: str = "default",
    ) -> Tuple[bool, Optional[str], int]:
        """
        Evaluates a user prompt turn:
        - If user prompt expresses decision-deferral, increments count.
        - If count >= threshold, returns (True, warning_message, count).
        - If user asserts agency/choice, resets consecutive deferral count to 0.

        Returns:
            (should_warn, warning_message, consecutive_deferrals)
        """
        state = self.get_state(user_id, tenant_id)

        # 1. Agency assertion resets consecutive deferral counter
        if self.is_agency_assertion(prompt):
            state.consecutive_deferrals = 0
            state.warning_triggered = False
            return False, None, 0

        # 2. Check deferral pattern
        if self.is_decision_deferral(prompt):
            state.consecutive_deferrals += 1
            state.total_deferrals += 1
            state.last_deferral_timestamp = time.time()
            state.history.append(prompt[:100])

            if state.consecutive_deferrals >= self.threshold:
                state.warning_triggered = True
                state.warning_count += 1
                return True, self.warning_message, state.consecutive_deferrals

        return False, None, state.consecutive_deferrals

    def reset_user(self, user_id: str, tenant_id: str = "default") -> None:
        k = self._key(user_id, tenant_id)
        if k in self._states:
            self._states[k].consecutive_deferrals = 0
            self._states[k].warning_triggered = False


# Default shared singleton instance
default_over_reliance_guard = OverRelianceGuard()
