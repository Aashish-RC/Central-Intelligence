"""🚩 Crown Jewel: 4-Tier PII & Telemetry Scrubber (Layer 10: Feature 10.30; Layer 14: Feature 14.19).

High-speed regex + Luhn + pattern pipeline intercepting data before logs, external models,
or persistent storage. Directs payloads to 4 isolated tiers:
- Tier 1: Non-PII telemetry metrics (90–365 days retention) -> SigNoz / OTel
- Tier 2: Redacted chat snippets (14–30 days retention) -> Ephemeral diagnostic store
- Tier 3: Tamper-proof encrypted action audit (365 days compliance) -> Merkle ledger
- Tier 4: Zero-Data Retention (in-memory volatile buffer, 0 disk footprint, 30s RAM purge)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Union

from .detectors import PIIDetector
from .models import DataClass, PIIFinding, RetentionPolicy, ScrubbedData, ScrubberConfig
from .redactors import Redactor
from .tier1_telemetry import Tier1TelemetrySink
from .tier2_diagnostic import Tier2DiagnosticStore
from .tier3_audit import Tier3AuditLedger
from .tier4_zdr import Tier4ZDR


class FourTierPIIScrubber:
    """Enterprise 4-Tier PII Sanitizer & Telemetry Router."""

    def __init__(
        self,
        config: Optional[ScrubberConfig] = None,
        unified_ledger: Optional[Any] = None,
    ):
        self.config = config or ScrubberConfig()
        self.detector = PIIDetector()
        self.redactor = Redactor(self.detector)

        retention = self.config.default_retention
        self.tier1 = Tier1TelemetrySink(default_ttl_days=retention.telemetry_ttl)
        self.tier2 = Tier2DiagnosticStore(default_ttl_days=retention.diagnostic_ttl)
        self.tier3 = Tier3AuditLedger(
            encryption_key=self.config.encryption_key,
            default_ttl_days=retention.audit_ttl,
            unified_ledger=unified_ledger,
        )
        self.tier4 = Tier4ZDR(default_ttl_seconds=retention.zdr_ttl_seconds)

    def scrub(
        self,
        data: Any,
        data_class: DataClass = DataClass.DIAGNOSTIC,
        user_id: str = "anon",
        retention_policy: Optional[RetentionPolicy] = None,
        tenant_id: str = "default",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScrubbedData:
        """Sanitizes sensitive data and dispatches to the specified retention tier."""
        policy = retention_policy or self.config.default_retention

        # Normalize text representation for hashing and PII scanning
        if isinstance(data, str):
            text_repr = data
        elif isinstance(data, (dict, list)):
            text_repr = json.dumps(data, sort_keys=True)
        else:
            text_repr = str(data)

        raw_hash = hashlib.sha256(text_repr.encode("utf-8")).hexdigest()
        pii_findings: List[PIIFinding] = self.detector.detect(text_repr)

        # ----------------------------------------------------
        # Tier 1: Technical Telemetry
        # ----------------------------------------------------
        if data_class == DataClass.TELEMETRY:
            # Strip all PII; prepare metrics
            clean_text = self.redactor.strip_all_pii(text_repr)
            payload = data if isinstance(data, dict) else {"content": clean_text}
            clean_payload = {
                k: self.redactor.strip_all_pii(str(v)) if isinstance(v, str) else v
                for k, v in payload.items()
            }
            rec1 = self.tier1.store(
                clean_payload,
                user_id=user_id,
                retained_days=policy.telemetry_ttl,
            )
            return ScrubbedData(
                tier=1,
                stored=True,
                retained_days=policy.telemetry_ttl,
                data=clean_payload,
                findings=pii_findings,
                raw_sha256=raw_hash,
                metadata={"metric_id": rec1.metric_id, **(metadata or {})},
            )

        # ----------------------------------------------------
        # Tier 2: Redacted Diagnostic Snippet
        # ----------------------------------------------------
        elif data_class == DataClass.DIAGNOSTIC:
            redacted = self.redactor.redact(text_repr, pii_findings)
            rec2 = self.tier2.store(
                redacted_content=redacted,
                user_id=user_id,
                session_id=session_id,
                ttl_days=policy.diagnostic_ttl,
                metadata=metadata,
            )
            return ScrubbedData(
                tier=2,
                stored=True,
                retained_days=policy.diagnostic_ttl,
                data=redacted,
                findings=pii_findings,
                raw_sha256=raw_hash,
                metadata={"record_id": rec2.record_id, **(metadata or {})},
            )

        # ----------------------------------------------------
        # Tier 3: Encrypted Compliance Audit
        # ----------------------------------------------------
        elif data_class == DataClass.AUDIT:
            rec3 = self.tier3.store(
                raw_payload=data,
                user_id=user_id,
                action=metadata.get("action", "agent_action") if metadata else "agent_action",
                tenant_id=tenant_id,
                ttl_days=policy.audit_ttl,
                metadata=metadata,
            )
            return ScrubbedData(
                tier=3,
                stored=True,
                retained_days=policy.audit_ttl,
                data=rec3.encrypted_payload,
                findings=pii_findings,
                raw_sha256=raw_hash,
                metadata={"audit_id": rec3.audit_id, "payload_hash": rec3.payload_hash, **(metadata or {})},
            )

        # ----------------------------------------------------
        # Tier 4: Zero-Data Retention (ZDR)
        # ----------------------------------------------------
        elif data_class == DataClass.ZDR:
            item_id = self.tier4.hold_in_memory(
                payload=data,
                user_id=user_id,
                ttl_seconds=policy.zdr_ttl_seconds,
            )
            return ScrubbedData(
                tier=4,
                stored=False,
                retained_days=0,
                data=data,
                findings=pii_findings,
                raw_sha256=raw_hash,
                metadata={"zdr_item_id": item_id, "volatile_ttl_seconds": policy.zdr_ttl_seconds, **(metadata or {})},
            )

        raise ValueError(f"Unknown data class: {data_class}")

    def purge_all(self, user_id: str) -> Dict[str, int]:
        """Right-to-erasure propagation: purges user data across all 4 tiers."""
        t1_count = self.tier1.purge(user_id)
        t2_count = self.tier2.purge(user_id)
        t3_count = self.tier3.purge(user_id)
        t4_count = self.tier4.purge(user_id)

        return {
            "tier1_telemetry_purged": t1_count,
            "tier2_diagnostic_purged": t2_count,
            "tier3_audit_purged": t3_count,
            "tier4_zdr_purged": t4_count,
            "total_purged": t1_count + t2_count + t3_count + t4_count,
        }
