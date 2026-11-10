"""
Multi-Account Abuse Detector (Feature 10.48)
Detects individuals spinning up multiple duplicate or disposable accounts from the same
IP address, subnet, or device fingerprint to evade restrictions, quotas, or rate limits.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class MultiAccountAssessment:
    is_flagged: bool
    action: str  # "allow", "flag", "block"
    account_count: int
    risk_score: float
    reason: str
    correlated_accounts: List[str] = field(default_factory=list)


class MultiAccountDetector:
    """
    Detects Sybil registrations and multi-account creation abuse (Feature 10.48).
    Flags or blocks registration when account velocity from an IP or device exceeds threshold.
    """

    def __init__(
        self,
        ip_threshold: int = 5,
        device_threshold: int = 3,
        window_seconds: int = 86400,  # 24-hour evaluation window
    ):
        self.ip_threshold = ip_threshold
        self.device_threshold = device_threshold
        self.window_seconds = window_seconds

        # IP -> list of (user_id, timestamp)
        self._ip_history: Dict[str, List[Tuple[str, float]]] = {}
        # Device fingerprint -> list of (user_id, timestamp)
        self._device_history: Dict[str, List[Tuple[str, float]]] = {}

    def record_and_evaluate(
        self,
        user_id: str,
        email: str,
        ip_address: str,
        device_fingerprint: Optional[str] = None,
        tenant_id: str = "default",
    ) -> MultiAccountAssessment:
        now = time.time()
        cutoff = now - self.window_seconds

        # 1. Clean and update IP history
        ip_records = [
            (uid, t) for uid, t in self._ip_history.get(ip_address, [])
            if t > cutoff
        ]
        # Append new attempt
        ip_records.append((user_id, now))
        self._ip_history[ip_address] = ip_records

        correlated = list(set([uid for uid, _ in ip_records if uid != user_id]))
        ip_count = len(ip_records)

        # 2. Check Device Fingerprint if present
        dev_count = 0
        if device_fingerprint:
            dev_records = [
                (uid, t) for uid, t in self._device_history.get(device_fingerprint, [])
                if t > cutoff
            ]
            dev_records.append((user_id, now))
            self._device_history[device_fingerprint] = dev_records
            dev_count = len(dev_records)
            for uid, _ in dev_records:
                if uid != user_id and uid not in correlated:
                    correlated.append(uid)

        # 3. Decision Logic: 5th account from same IP is flagged (Feature 10.48 Acceptance)
        if ip_count >= self.ip_threshold or (device_fingerprint and dev_count >= self.device_threshold):
            action = "block" if ip_count > self.ip_threshold + 3 else "flag"
            reason = (
                f"Multi-account abuse detected: {ip_count} accounts created from IP '{ip_address}' "
                f"(threshold: {self.ip_threshold})."
            )
            return MultiAccountAssessment(
                is_flagged=True,
                action=action,
                account_count=ip_count,
                risk_score=min(1.0, 0.2 * ip_count),
                reason=reason,
                correlated_accounts=correlated,
            )

        return MultiAccountAssessment(
            is_flagged=False,
            action="allow",
            account_count=ip_count,
            risk_score=0.1 * ip_count,
            reason="Account creation velocity within normal thresholds.",
            correlated_accounts=correlated,
        )


# Global singleton instance
default_multi_account_detector = MultiAccountDetector()
