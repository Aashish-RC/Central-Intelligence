"""🚩 4-Tier Structured Log Router (Layer 14: Feature 14.19; Layer 10: Feature 10.30).

Intercepts all application logs, traces, and metrics, routing them through Layer 10's
4-Tier PII Scrubber before dispatch to external telemetry collectors or storage sinks:
- Tier 1 (Telemetry) -> SigNoz collector (90–365 days retention)
- Tier 2 (Diagnostic) -> Ephemeral store (14–30 days retention)
- Tier 3 (Action Audit) -> Unified Merkle Ledger (1 year encrypted compliance)
- Tier 4 (ZDR) -> In-memory volatile buffer only (0 disk/log persistence)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from control.observability.signoz import SigNozAdapter
from control.safety.pii import DataClass, FourTierPIIScrubber, RetentionPolicy, ScrubbedData

try:
    from control.safety.consent.c15t_adapter import C15tConsentAdapter, get_default_consent_adapter
except ImportError:
    C15tConsentAdapter = None
    get_default_consent_adapter = lambda: None

logger = logging.getLogger("control.observability.logging")


@dataclass
class LogEntry:
    content: str
    level: str = "INFO"
    user_id: str = "anon"
    tenant_id: str = "default"
    app_id: str = "default_app"
    log_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TieredLogRouter:
    """Enterprise 4-Tier Structured Log Router with automatic PII sanitization."""

    def __init__(
        self,
        scrubber: Optional[FourTierPIIScrubber] = None,
        signoz: Optional[SigNozAdapter] = None,
        consent_adapter: Optional[Any] = None,
        residency_enforcer: Optional[Any] = None,
    ):
        self.scrubber = scrubber or FourTierPIIScrubber()
        self.signoz = signoz or SigNozAdapter()
        self.consent_adapter = consent_adapter or (get_default_consent_adapter() if get_default_consent_adapter else None)
        self.residency_enforcer = residency_enforcer
        self._routed_logs: List[Dict[str, Any]] = []

    def route(
        self,
        entry: LogEntry,
        data_class: DataClass = DataClass.DIAGNOSTIC,
        privacy_mode: bool = False,
        retention_policy: Optional[RetentionPolicy] = None,
    ) -> ScrubbedData:
        """Routes log payload through the 4-tier PII scrubber to appropriate destination."""
        # Privacy mode (Feature 10.35) or c15t consent check
        user_in_privacy = privacy_mode
        if not user_in_privacy and self.consent_adapter:
            user_in_privacy = self.consent_adapter.is_privacy_mode(entry.user_id, entry.tenant_id)

        target_class = DataClass.ZDR if user_in_privacy else data_class

        # 1. Scrub through 4-Tier PII scrubber
        scrubbed = self.scrubber.scrub(
            data=entry.content,
            data_class=target_class,
            user_id=entry.user_id,
            retention_policy=retention_policy,
            tenant_id=entry.tenant_id,
            metadata={
                "log_id": entry.log_id,
                "level": entry.level,
                "app_id": entry.app_id,
                **(entry.metadata or {}),
            },
        )

        # 2. Check Data Residency Boundary (Feature 10.32)
        allow_external_dispatch = True
        if self.residency_enforcer:
            signoz_region = getattr(self.signoz, "region", "us")
            allow_external_dispatch = self.residency_enforcer.is_dispatch_allowed(
                user_id=entry.user_id,
                target_region=signoz_region,
                tenant_id=entry.tenant_id,
            )

        # 3. Dispatch to destination based on Tier
        if scrubbed.tier == 1 and allow_external_dispatch:
            # Telemetry -> SigNoz metric emission
            self.signoz.record_metric(
                name="log.telemetry.events",
                value=1.0,
                metric_type="counter",
                labels={
                    "level": entry.level,
                    "app_id": entry.app_id,
                    "tenant_id": entry.tenant_id,
                },
            )

        # Record route metadata
        self._routed_logs.append({
            "log_id": entry.log_id,
            "tier": scrubbed.tier,
            "user_id": entry.user_id if scrubbed.tier != 1 else "hashed",
            "stored": scrubbed.stored,
            "retained_days": scrubbed.retained_days,
            "findings_count": len(scrubbed.findings),
            "dispatched_external": allow_external_dispatch,
        })

        return scrubbed

    def get_routed_history(self) -> List[Dict[str, Any]]:
        return list(self._routed_logs)
