"""
Automated Log Retention Scheduler & Cleanup Engine (Layer 14: Feature 14.20).

Features:
- 14.20: User/tenant-configurable TTL policies per data class.
  - Automatically sweeps and purges expired diagnostic and telemetry logs past their retention TTL.
  - Strictly enforces c15t consent privacy mode: users with active privacy mode are assigned
    zero retention (0 days / ZDR volatile buffer only).
- Wires into Layer 10 4-Tier PII Scrubber and Layer 14 Tiered Log Router.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from control.safety.pii import DataClass, FourTierPIIScrubber, RetentionPolicy

logger = logging.getLogger("control.observability.logging.retention")

DEFAULT_RETENTION_TTLS: Dict[DataClass, int] = {
    DataClass.TELEMETRY: 365,
    DataClass.DIAGNOSTIC: 14,
    DataClass.AUDIT: 365,
    DataClass.ZDR: 0,
}


@dataclass
class RetentionPolicyOverride:
    """User- or tenant-specific TTL overrides."""
    user_id: str
    tenant_id: str = "default"
    telemetry_ttl_days: Optional[int] = None
    diagnostic_ttl_days: Optional[int] = None
    audit_ttl_days: Optional[int] = None

    def get_ttl_for(self, data_class: DataClass) -> Optional[int]:
        if data_class == DataClass.TELEMETRY:
            return self.telemetry_ttl_days
        if data_class == DataClass.DIAGNOSTIC:
            return self.diagnostic_ttl_days
        if data_class == DataClass.AUDIT:
            return self.audit_ttl_days
        return None


class RetentionScheduler:
    """
    Coordinates data class retention policies, consent overrides, and scheduled deletion of expired logs.
    """

    def __init__(
        self,
        scrubber: Optional[FourTierPIIScrubber] = None,
        consent_manager: Optional[Any] = None,
        log_router: Optional[Any] = None,
    ) -> None:
        self.scrubber = scrubber or FourTierPIIScrubber()
        self.consent = consent_manager
        self.log_router = log_router
        self._user_overrides: Dict[str, Any] = {}

        # Expose individual store tiers for direct cleanup
        self.tier1 = getattr(self.scrubber, "tier1", None)
        self.tier2 = getattr(self.scrubber, "tier2", None)
        self.tier3 = getattr(self.scrubber, "tier3", None)

    def _get_consent(self) -> Any:
        if self.consent is None:
            try:
                from control.safety.consent.c15t_adapter import default_c15t_adapter
                self.consent = default_c15t_adapter
            except ImportError:
                pass
        return self.consent

    def set_user_override(
        self,
        user_id: str,
        policy_or_ttl: Union[RetentionPolicy, RetentionPolicyOverride, int, Dict[DataClass, int]],
        tenant_id: str = "default",
        diagnostic_ttl_days: Optional[int] = None,
        audit_ttl_days: Optional[int] = None,
    ) -> Any:
        """Sets custom retention TTLs for a specific user or tenant."""
        if isinstance(policy_or_ttl, int) and diagnostic_ttl_days is not None:
            override = RetentionPolicyOverride(
                user_id=user_id,
                tenant_id=tenant_id,
                telemetry_ttl_days=policy_or_ttl,
                diagnostic_ttl_days=diagnostic_ttl_days,
                audit_ttl_days=audit_ttl_days,
            )
            self._user_overrides[user_id] = override
            return override

        self._user_overrides[user_id] = policy_or_ttl
        return policy_or_ttl

    def get_user_policy(self, user_id: str) -> Optional[Any]:
        """Returns registered user policy override if any."""
        return self._user_overrides.get(user_id)

    def get_retention(
        self,
        user_id: str,
        data_class: DataClass | str,
        tenant_id: str = "default",
    ) -> RetentionPolicy | int:
        """
        Determines effective retention policy or days for a given user and data class (Feature 14.20).
        If user is in privacy mode -> returns RetentionPolicy(ttl_days=0) (ZDR).
        """
        dc = DataClass(data_class) if isinstance(data_class, str) else data_class

        # Check c15t consent privacy mode (Feature 10.35)
        consent = self.consent or self._get_consent()
        if consent and hasattr(consent, "is_privacy_mode"):
            try:
                if consent.is_privacy_mode(user_id):
                    return RetentionPolicy(ttl_days=0)
            except TypeError:
                if consent.is_privacy_mode(user_id, tenant_id):
                    return RetentionPolicy(ttl_days=0)

        defaults = {
            DataClass.TELEMETRY: 365,
            DataClass.DIAGNOSTIC: 14,
            DataClass.AUDIT: 365,
            DataClass.ZDR: 0,
        }

        user_override = self.get_user_policy(user_id)
        if user_override is not None:
            if isinstance(user_override, RetentionPolicyOverride):
                val = user_override.get_ttl_for(dc)
                if val is not None:
                    return val
            elif isinstance(user_override, RetentionPolicy):
                return user_override
            elif isinstance(user_override, dict):
                if dc in user_override:
                    return user_override[dc]
            elif isinstance(user_override, int):
                return user_override

        return defaults.get(dc, 14)

    def get_retention_days(
        self,
        user_id: str,
        data_class: DataClass | str,
        tenant_id: str = "default",
    ) -> int:
        """Helper that always returns an integer number of days."""
        policy = self.get_retention(user_id, data_class, tenant_id=tenant_id)
        if isinstance(policy, RetentionPolicy):
            return policy.ttl_days if policy.ttl_days is not None else policy.diagnostic_ttl
        return int(policy)

    def cleanup_expired(self, current_time: Optional[float] = None) -> Dict[str, int]:
        """
        Scheduled job: delete logs past their TTL (Feature 14.20).
        Acceptance: Logs older than 14 days deleted.
        """
        purged_tier1 = 0
        purged_tier2 = 0
        purged_tier3 = 0

        for store_name, store in [
            ("tier1", self.tier1),
            ("tier2", self.tier2),
            ("tier3", self.tier3),
        ]:
            if store is not None:
                if hasattr(store, "delete_expired"):
                    count = store.delete_expired(current_time=current_time)
                    if store_name == "tier1":
                        purged_tier1 += count
                    elif store_name == "tier2":
                        purged_tier2 += count
                    elif store_name == "tier3":
                        purged_tier3 += count
                elif hasattr(store, "_evict_expired"):
                    count = store._evict_expired()
                    if store_name == "tier2":
                        purged_tier2 += count

        total_purged = purged_tier1 + purged_tier2 + purged_tier3
        logger.info(
            "Log retention sweep completed: %d total expired logs deleted (tier1=%d, tier2=%d, tier3=%d)",
            total_purged,
            purged_tier1,
            purged_tier2,
            purged_tier3,
        )
        return {
            "tier1_purged": purged_tier1,
            "tier2_purged": purged_tier2,
            "tier3_purged": purged_tier3,
            "total_purged": total_purged,
        }


# Global default singleton
default_retention_scheduler = RetentionScheduler()
