"""
Billing Quota Gaming & Free-Tier Abuse Detection (Layer 13: Feature 13.18).

Features:
- 13.18: Detects automated misuse and churn of free-tier quotas.
  Correlates IP addresses, device fingerprints, and canonical email addresses to identify
  users who hit their free-tier usage limit and immediately create a new account to evade payment.
- Bridges to Layer 10 Abuse Detectors (Features 10.48, 10.49).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("control.billing.abuse.quota_gaming")


@dataclass
class QuotaGamingResult:
    """Assessment of account registration or usage for free-tier gaming."""
    is_gaming: bool
    risk_score: float  # 0.0 to 1.0
    action: str  # "allow", "flag", "block"
    reasons: List[str] = field(default_factory=list)
    prior_exhausted_accounts: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class BillingQuotaGamingDetector:
    """
    Tracks free-tier limit exhaustions and flags correlated new account registrations (Feature 13.18).
    """

    def __init__(
        self,
        safety_quota_detector: Optional[Any] = None,
        safety_multi_account_detector: Optional[Any] = None,
    ) -> None:
        self._safety_quota_detector = safety_quota_detector
        self._safety_multi_detector = safety_multi_account_detector

        # IP -> list of user_ids that exhausted free-tier
        self._ip_exhausted_accounts: Dict[str, List[str]] = {}
        # Device fingerprint -> list of user_ids
        self._device_exhausted_accounts: Dict[str, List[str]] = {}
        # Canonical email -> list of user_ids
        self._email_canonical_exhausted: Dict[str, List[str]] = {}

    def _canonicalize_email(self, email: str) -> str:
        """Strips plus tags (e.g. user+1@gmail.com -> user@gmail.com)."""
        if not email or "@" not in email:
            return email.lower()
        local, domain = email.split("@", 1)
        local_base = local.split("+")[0].replace(".", "").lower()
        return f"{local_base}@{domain.lower()}"

    def _get_safety_quota_detector(self) -> Any:
        if self._safety_quota_detector is None:
            try:
                from control.safety.abuse.quota_gaming_detector import default_quota_gaming_detector
                self._safety_quota_detector = default_quota_gaming_detector
            except ImportError:
                pass
        return self._safety_quota_detector

    def record_quota_exhaustion(
        self,
        user_id: str,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
    ) -> None:
        """
        Records that an account has completely exhausted its free-tier allocation.
        """
        if ip_address:
            self._ip_exhausted_accounts.setdefault(ip_address, []).append(user_id)
        if device_fingerprint:
            self._device_exhausted_accounts.setdefault(device_fingerprint, []).append(user_id)
        if email:
            canonical = self._canonicalize_email(email)
            self._email_canonical_exhausted.setdefault(canonical, []).append(user_id)

        logger.info(
            "Recorded free-tier exhaustion for user '%s' (IP: %s, Device: %s)",
            user_id,
            ip_address,
            device_fingerprint,
        )

    def evaluate_new_account(
        self,
        user_id: str,
        email: str,
        ip_address: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
    ) -> QuotaGamingResult:
        """
        Evaluates new account creation against free-tier gaming patterns (Feature 13.18).
        Acceptance: User hitting limit then creating new account is flagged.
        """
        reasons: List[str] = []
        prior_exhausted: List[str] = []
        risk_score = 0.0

        # 1. Correlate with IP addresses of previously exhausted accounts
        if ip_address and ip_address in self._ip_exhausted_accounts:
            matched = self._ip_exhausted_accounts[ip_address]
            prior_exhausted.extend(matched)
            reasons.append(
                f"Same IP '{ip_address}' previously exhausted free-tier on {len(matched)} account(s): {', '.join(matched[:3])}"
            )
            risk_score += 0.6

        # 2. Correlate with device fingerprints
        if device_fingerprint and device_fingerprint in self._device_exhausted_accounts:
            matched = self._device_exhausted_accounts[device_fingerprint]
            prior_exhausted.extend(matched)
            reasons.append(
                f"Device fingerprint previously associated with exhausted free-tier accounts: {', '.join(matched[:3])}"
            )
            risk_score += 0.8

        # 3. Canonical email alias reuse (e.g. user+1@gmail.com after user@gmail.com exhausted)
        canonical = self._canonicalize_email(email)
        if canonical in self._email_canonical_exhausted:
            matched = self._email_canonical_exhausted[canonical]
            prior_exhausted.extend(matched)
            reasons.append(
                f"Email canonical base '{canonical}' already exhausted free-tier quota on account: {matched[0]}"
            )
            risk_score += 0.9

        # 4. Bridge to Layer 10 Quota Gaming Detector (e.g. disposable email check)
        l10_detector = self._get_safety_quota_detector()
        if l10_detector and hasattr(l10_detector, "evaluate_account"):
            try:
                l10_assessment = l10_detector.evaluate_account(user_id=user_id, email=email)
                if l10_assessment.is_gaming:
                    reasons.extend(l10_assessment.reasons)
                    risk_score = max(risk_score, l10_assessment.risk_score)
            except Exception:
                pass

        is_gaming = len(prior_exhausted) > 0 or risk_score >= 0.5
        if risk_score >= 0.8:
            action = "block"
        elif is_gaming:
            action = "flag"
        else:
            action = "allow"

        if is_gaming:
            logger.warning(
                "Free-tier quota gaming flagged for user '%s' (%s, IP: %s): %s",
                user_id,
                email,
                ip_address,
                "; ".join(reasons),
            )

        return QuotaGamingResult(
            is_gaming=is_gaming,
            risk_score=min(1.0, risk_score),
            action=action,
            reasons=reasons,
            prior_exhausted_accounts=list(set(prior_exhausted)),
        )


# Global default singleton
default_billing_quota_gaming_detector = BillingQuotaGamingDetector()
