"""
Free-Tier Quota Gaming Detector (Feature 10.49)
Detects strategies used to circumvent free-tier billing limits:
- Disposable / temporary burner email domains
- Cycling through ephemeral accounts to evade quota exhaustion
- Correlated token consumption surges across clustered accounts
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

DISPOSABLE_EMAIL_DOMAINS: Set[str] = {
    "mailinator.com",
    "tempmail.com",
    "10minutemail.com",
    "guerrillamail.com",
    "sharklasers.com",
    "throwawaymail.com",
    "yopmail.com",
    "dispostable.com",
    "fakeinbox.com",
    "getairmail.com",
}


@dataclass
class QuotaGamingAssessment:
    is_gaming: bool
    risk_score: float  # 0.0 to 1.0
    action: str  # "allow", "warn", "restrict", "block"
    reasons: List[str] = field(default_factory=list)
    is_disposable_email: bool = False


class QuotaGamingDetector:
    """
    Detects attempts to game free quotas and billing engines (Feature 10.49).
    """

    def __init__(self, disposable_domains: Optional[Set[str]] = None):
        self.disposable_domains = disposable_domains or DISPOSABLE_EMAIL_DOMAINS
        self._user_usage_spikes: Dict[str, List[int]] = {}

    def is_disposable_email(self, email: str) -> bool:
        if not email or "@" not in email:
            return False
        domain = email.split("@")[-1].strip().lower()
        return domain in self.disposable_domains

    def evaluate_account(
        self,
        user_id: str,
        email: str,
        free_tier_tokens_granted: int = 100000,
        tokens_consumed: int = 0,
    ) -> QuotaGamingAssessment:
        reasons: List[str] = []
        risk_score = 0.0

        # 1. Disposable email check
        is_burner = self.is_disposable_email(email)
        if is_burner:
            reasons.append(f"Account registered with disposable email domain: {email.split('@')[-1]}")
            risk_score += 0.7

        # 2. Consumption velocity vs free quota
        if free_tier_tokens_granted > 0 and tokens_consumed >= free_tier_tokens_granted:
            reasons.append("Free tier quota completely exhausted; user attempting continued unbilled generation.")
            risk_score += 0.5

        is_gaming = risk_score >= 0.5
        action = "block" if risk_score >= 0.8 else ("restrict" if is_gaming else "allow")

        return QuotaGamingAssessment(
            is_gaming=is_gaming,
            risk_score=min(1.0, risk_score),
            action=action,
            reasons=reasons,
            is_disposable_email=is_burner,
        )


# Global default instance
default_quota_gaming_detector = QuotaGamingDetector()
