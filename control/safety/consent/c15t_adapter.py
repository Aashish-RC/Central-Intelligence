"""
c15t Consent Management Adapter (10.29, 10.35)
Implements explicit opt-in consent for telemetry, diagnostic recording, and model training,
with per-user privacy mode (zero retention, no external training, no persistent logging).
Compatible with c15t open-source consent management specifications (Apache-2.0).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from control.safety.production_guard import (
    fail_closed_in_production,
    require_live_adapter,
)


class ConsentPurpose(str, Enum):
    TELEMETRY = "telemetry"
    DIAGNOSTICS = "diagnostics"
    MODEL_TRAINING = "model_training"
    EXTERNAL_DISPATCH = "external_dispatch"
    ANALYTICS = "analytics"


@dataclass
class ConsentRecord:
    user_id: str
    tenant_id: str = "default"
    purposes: Dict[str, bool] = field(default_factory=dict)
    privacy_mode: bool = False
    opt_in_timestamp: Optional[float] = None
    revoked_timestamp: Optional[float] = None
    version: str = "1.0.0"
    receipt_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_receipt_hash(self) -> str:
        payload = {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "purposes": sorted(self.purposes.items()),
            "privacy_mode": self.privacy_mode,
            "opt_in_timestamp": self.opt_in_timestamp,
            "version": self.version,
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class C15tConsentAdapter:
    """
    c15t consent management adapter providing explicit consent tracking
    and enforcing Privacy Mode (Feature 10.35).
    """

    def __init__(self, default_opt_in: bool = False, _defer_prod_check: bool = False):
        # By default, GDPR/privacy regulations require opt-in (default False)
        self.default_opt_in = default_opt_in
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("c15t")
        )
        self._records: Dict[str, ConsentRecord] = {}

    def _key(self, user_id: str, tenant_id: str = "default") -> str:
        return f"{tenant_id}:{user_id}"

    def get_consent_record(self, user_id: str, tenant_id: str = "default") -> ConsentRecord:
        key = self._key(user_id, tenant_id)
        if key not in self._records:
            record = ConsentRecord(
                user_id=user_id,
                tenant_id=tenant_id,
                purposes={p.value: self.default_opt_in for p in ConsentPurpose},
                privacy_mode=False,
            )
            record.receipt_hash = record.calculate_receipt_hash()
            self._records[key] = record
        return self._records[key]

    def grant_consent(
        self,
        user_id: str,
        purposes: List[str | ConsentPurpose],
        tenant_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConsentRecord:
        """Explicitly grants consent for specific purposes."""
        record = self.get_consent_record(user_id, tenant_id)
        for p in purposes:
            p_val = p.value if isinstance(p, ConsentPurpose) else str(p)
            record.purposes[p_val] = True

        record.opt_in_timestamp = time.time()
        if metadata:
            record.metadata.update(metadata)
        record.receipt_hash = record.calculate_receipt_hash()
        return record

    def revoke_consent(
        self,
        user_id: str,
        purposes: Optional[List[str | ConsentPurpose]] = None,
        tenant_id: str = "default",
    ) -> ConsentRecord:
        """Revokes consent for specific purposes or all purposes if omitted."""
        record = self.get_consent_record(user_id, tenant_id)
        if purposes is None:
            for p in list(record.purposes.keys()):
                record.purposes[p] = False
        else:
            for p in purposes:
                p_val = p.value if isinstance(p, ConsentPurpose) else str(p)
                record.purposes[p_val] = False

        record.revoked_timestamp = time.time()
        record.receipt_hash = record.calculate_receipt_hash()
        return record

    def set_privacy_mode(
        self,
        user_id: str,
        enabled: bool = True,
        tenant_id: str = "default",
    ) -> ConsentRecord:
        """
        Enables or disables Privacy Mode (Feature 10.35).
        When enabled:
        - All telemetry, logging, and model training permissions are overridden to False.
        - Zero Data Retention (ZDR) is strictly mandated.
        """
        record = self.get_consent_record(user_id, tenant_id)
        record.privacy_mode = enabled
        if enabled:
            # Overrule all collection purposes
            record.purposes[ConsentPurpose.TELEMETRY.value] = False
            record.purposes[ConsentPurpose.DIAGNOSTICS.value] = False
            record.purposes[ConsentPurpose.MODEL_TRAINING.value] = False
            record.purposes[ConsentPurpose.ANALYTICS.value] = False

        record.receipt_hash = record.calculate_receipt_hash()
        return record

    def is_privacy_mode(self, user_id: str, tenant_id: str = "default") -> bool:
        """Returns True if the user or tenant has enabled privacy mode."""
        key = self._key(user_id, tenant_id)
        if key in self._records and self._records[key].privacy_mode:
            return True
        # Check if user has privacy mode enabled across any recorded tenant
        for r in self._records.values():
            if r.user_id == user_id and r.privacy_mode:
                return True
        return False

    def has_consent(
        self,
        user_id: str,
        purpose: str | ConsentPurpose,
        tenant_id: str = "default",
    ) -> bool:
        """
        Evaluates whether a user has active consent for a given purpose.
        Returns False immediately if user is in privacy mode.
        """
        p_val = purpose.value if isinstance(purpose, ConsentPurpose) else str(purpose)
        record = self.get_consent_record(user_id, tenant_id)

        # Privacy mode denies all data collection/training
        if record.privacy_mode:
            return False

        return record.purposes.get(p_val, self.default_opt_in)

    def export_audit_receipt(self, user_id: str, tenant_id: str = "default") -> Dict[str, Any]:
        """Generates cryptographic compliance receipt for GDPR Article 7 audit logs."""
        record = self.get_consent_record(user_id, tenant_id)
        return {
            "user_id": record.user_id,
            "tenant_id": record.tenant_id,
            "purposes": record.purposes,
            "privacy_mode": record.privacy_mode,
            "opt_in_timestamp": record.opt_in_timestamp,
            "revoked_timestamp": record.revoked_timestamp,
            "version": record.version,
            "receipt_hash": record.calculate_receipt_hash(),
        }


# Global singleton instance for system-wide consent checking
_default_consent_adapter = C15tConsentAdapter()


def get_default_consent_adapter() -> C15tConsentAdapter:
    return _default_consent_adapter


def set_default_consent_adapter(adapter: C15tConsentAdapter) -> None:
    global _default_consent_adapter
    _default_consent_adapter = adapter
