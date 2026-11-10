"""
Safeguards for Minors: Age-Gating & Child-Safety Mode (Feature 10.44).

Features:
- 10.44: Age-gating & child safety mode. Identifies minors via L12 Identity verification,
  restricts adult/mature content, disables high-risk tools (payments, raw browser automation, shell execution),
  and applies strict safety guardrails.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("control.safety.wellbeing.minor_safeguards")


@dataclass
class MinorStatus:
    """Status assessment for a user regarding minor protections."""
    user_id: str
    is_minor: bool
    age: Optional[int] = None
    child_safety_mode_active: bool = False
    verification_source: str = "unverified"
    restricted_tools: List[str] = field(default_factory=list)


@dataclass
class MinorSafetyCheckResult:
    """Content or action safety check result under child-safety rules."""
    allowed: bool
    action: str  # "allow", "block"
    reason: Optional[str] = None
    violated_category: Optional[str] = None


class MinorSafeguardsEnforcer:
    """
    Enforces child-safety constraints, restricted tool access, and content filtering for minors.
    """

    # High-risk tools prohibited for minors
    DEFAULT_DISALLOWED_TOOLS: Set[str] = {
        "payment",
        "payment_processing",
        "stripe",
        "checkout",
        "transfer_funds",
        "financial_transaction",
        "crypto_wallet",
        "browser_automation",
        "puppeteer",
        "playwright",
        "raw_browser",
        "terminal_exec",
        "shell_exec",
        "bash",
        "code_eval",
    }

    # Adult / mature content patterns strictly blocked for minors
    ADULT_CONTENT_PATTERNS = [
        (re.compile(r"\b(pornography|porn|erotica|nsfw|sexually\s+explicit|xxx|hardcore\s+sex|strip\s+club)\b", re.I), "adult_content"),
        (re.compile(r"\b(dating\s+apps?\s+for\s+hookups?|casual\s+hookups?|adult\s+dating)\b", re.I), "adult_dating"),
        (re.compile(r"\b(vape|vaping|e-cigarette|nicotine|tobacco\s+products?|buy\s+cigarettes)\b", re.I), "age_restricted_substances"),
        (re.compile(r"\b(buy\s+alcohol|liquor\s+store|wine\s+delivery|order\s+beer|illicit\s+drugs|cocaine|methamphetamine|fentanyl)\b", re.I), "substance_abuse"),
        (re.compile(r"\b(online\s+casino|sports\s+betting|gamble\s+real\s+money|slot\s+machines?|poker\s+for\s+cash)\b", re.I), "gambling"),
    ]

    def __init__(
        self,
        minor_age_threshold: int = 18,
        disallowed_tools: Optional[Set[str]] = None,
        keycloak_adapter: Optional[Any] = None,
    ):
        self.minor_age_threshold = minor_age_threshold
        self.disallowed_tools = set(disallowed_tools) if disallowed_tools is not None else set(self.DEFAULT_DISALLOWED_TOOLS)
        self._keycloak = keycloak_adapter
        self._user_age_cache: Dict[str, MinorStatus] = {}

    def _get_keycloak(self) -> Any:
        if self._keycloak is None:
            try:
                from control.identity.keycloak_adapter import default_keycloak_adapter
                self._keycloak = default_keycloak_adapter
            except ImportError:
                pass
        return self._keycloak

    def register_user_age(
        self,
        user_id: str,
        age: Optional[int] = None,
        birthdate_iso: Optional[str] = None,
        is_minor_override: Optional[bool] = None,
    ) -> MinorStatus:
        """Manually registers or updates the age status for a user."""
        computed_age = age
        if computed_age is None and birthdate_iso:
            try:
                b_date = datetime.strptime(birthdate_iso, "%Y-%m-%d").date()
                today = date.today()
                computed_age = today.year - b_date.year - ((today.month, today.day) < (b_date.month, b_date.day))
            except ValueError:
                pass

        if is_minor_override is not None:
            is_minor = is_minor_override
        elif computed_age is not None:
            is_minor = computed_age < self.minor_age_threshold
        else:
            is_minor = False

        status = MinorStatus(
            user_id=user_id,
            is_minor=is_minor,
            age=computed_age,
            child_safety_mode_active=is_minor,
            verification_source="manual_registration" if age or birthdate_iso else "override",
            restricted_tools=list(self.disallowed_tools) if is_minor else [],
        )
        self._user_age_cache[user_id] = status
        return status

    def get_minor_status(self, user_id: str) -> MinorStatus:
        """
        Retrieves or verifies minor status against L12 Identity (Keycloak).
        """
        if user_id in self._user_age_cache:
            return self._user_age_cache[user_id]

        # Query Keycloak adapter if available
        kc = self._get_keycloak()
        if kc and hasattr(kc, "get_user"):
            try:
                user_record = kc.get_user(user_id)
                attrs = getattr(user_record, "attributes", {})
                roles = getattr(user_record, "roles", set())

                # Check explicit minor role or attributes
                if "minor" in roles or attrs.get("is_minor") is True:
                    return self.register_user_age(user_id, is_minor_override=True)

                if "age" in attrs:
                    return self.register_user_age(user_id, age=int(attrs["age"]))

                if "birthdate" in attrs:
                    return self.register_user_age(user_id, birthdate_iso=str(attrs["birthdate"]))
            except Exception as e:
                logger.debug("Could not resolve user '%s' in Keycloak: %s", user_id, e)

        # Default to non-minor if no identity records indicate minor status
        status = MinorStatus(
            user_id=user_id,
            is_minor=False,
            child_safety_mode_active=False,
            verification_source="default",
            restricted_tools=[],
        )
        self._user_age_cache[user_id] = status
        return status

    def is_tool_allowed(self, user_id: str, tool_name: str) -> Tuple[bool, Optional[str]]:
        """
        Verifies whether an agent tool invocation is permissible for the user (Feature 10.44).
        Minors are blocked from financial/payment and browser automation tools.
        """
        status = self.get_minor_status(user_id)
        if not status.is_minor:
            return True, None

        normalized_tool = tool_name.strip().lower()
        if normalized_tool in self.disallowed_tools:
            reason = (
                f"Action blocked: Tool '{tool_name}' is disabled for minor users under child-safety mode."
            )
            logger.warning("Blocked tool '%s' for minor user '%s'", tool_name, user_id)
            return False, reason

        return True, None

    def evaluate_content(self, text: str, user_id: str) -> MinorSafetyCheckResult:
        """
        Verifies that prompt or model response is age-appropriate for minor users (Feature 10.44).
        Strictly blocks adult/sexually explicit, gambling, and age-restricted substance content.
        """
        status = self.get_minor_status(user_id)
        if not status.is_minor:
            return MinorSafetyCheckResult(allowed=True, action="allow")

        if not text:
            return MinorSafetyCheckResult(allowed=True, action="allow")

        for pattern, category in self.ADULT_CONTENT_PATTERNS:
            match = pattern.search(text)
            if match:
                reason = (
                    f"Access restricted: Content involving {category.replace('_', ' ')} "
                    f"is prohibited under child-safety mode."
                )
                logger.warning(
                    "Minor user '%s' blocked for category '%s' (matched: '%s')",
                    user_id,
                    category,
                    match.group(0),
                )
                return MinorSafetyCheckResult(
                    allowed=False,
                    action="block",
                    reason=reason,
                    violated_category=category,
                )

        return MinorSafetyCheckResult(allowed=True, action="allow")


# Default global singleton
default_minor_safeguards = MinorSafeguardsEnforcer()
