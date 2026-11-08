"""Action Classifier: Inspects browser actions and classifies consequential risks."""

import re
from typing import Optional, Tuple
from ..core.interfaces import BaseActionClassifier
from ..core.models import ActionRiskLevel, BrowserAction, BrowserActionType

CONSEQUENTIAL_SELECTORS = [
    re.compile(r"(?:submit|buy|checkout|purchase|pay|order|confirm-payment|confirm|payment)", re.I),
    re.compile(r"(?:delete|destroy|purge|remove|drop-table)", re.I),
    re.compile(r"(?:login|sign-in|authenticate|authorize|oauth)", re.I),
    re.compile(r"input\[type=['\"]?password['\"]?\]", re.I),
]

SENSITIVE_TEXT_PATTERNS = [
    re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"),  # Credit Card
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),        # SSN
    re.compile(r"\b(?:sk-[a-zA-Z0-9]{32,}|ghp_[a-zA-Z0-9]{20,})\b"), # API Key
]


class ActionClassifier(BaseActionClassifier):
    """Identifies actions that cause financial, identity, or data-mutating side effects."""

    def classify_action(
        self, action: BrowserAction, current_url: Optional[str] = None
    ) -> Tuple[ActionRiskLevel, Optional[str]]:
        # 1. Inherently consequential action types
        if action.action_type in (
            BrowserActionType.PAYMENT_CHECKOUT,
            BrowserActionType.DELETE_DATA,
            BrowserActionType.AUTH_LOGIN,
            BrowserActionType.SUBMIT_FORM,
        ):
            reason = f"Consequential action type '{action.action_type.value}': triggers state mutation, transaction, or auth."
            return ActionRiskLevel.CONSEQUENTIAL, reason

        # 2. Check Click Target Selectors
        if action.action_type == BrowserActionType.CLICK and action.target_selector:
            for pat in CONSEQUENTIAL_SELECTORS:
                if pat.search(action.target_selector):
                    reason = f"Consequential click target matching '{pat.pattern}': potential transaction or deletion."
                    return ActionRiskLevel.CONSEQUENTIAL, reason

        # 3. Check Input Text and Form Fields
        if action.action_type == BrowserActionType.TYPE_TEXT:
            if action.target_selector:
                for pat in CONSEQUENTIAL_SELECTORS:
                    if pat.search(action.target_selector):
                        reason = f"Typing into sensitive credential/auth input '{action.target_selector}'."
                        return ActionRiskLevel.CONSEQUENTIAL, reason

            if action.payload_text:
                for pat in SENSITIVE_TEXT_PATTERNS:
                    if pat.search(action.payload_text):
                        reason = "Payload contains sensitive financial or credential data."
                        return ActionRiskLevel.CONSEQUENTIAL, reason

            return ActionRiskLevel.MODERATE, None

        # 4. Read-only navigation, scroll, screenshot, DOM extraction are safe
        return ActionRiskLevel.SAFE, None
