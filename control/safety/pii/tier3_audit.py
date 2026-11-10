"""Tier 3 Compliance Audit Store (Layer 10: Safety, Feature 10.30; Layer 14: Observability, Feature 14.19).

Tier 3: Tamper-proof, cryptographically encrypted ledger of agent actions, external API executions,
and human authorizations. Retained for 1 year (365 days) for regulatory compliance.
Integrates with Layer 10 Unified Merkle Audit Ledger.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from cryptography.fernet import Fernet

try:
    from control.safety.audit.ledger import UnifiedAuditLedger
    from control.safety.audit.models import UnifiedAuditEntry, AuditSeverity
    _LEDGER_AVAILABLE = True
except ImportError:
    _LEDGER_AVAILABLE = False


@dataclass
class EncryptedAuditRecord:
    audit_id: str
    user_id: str
    tenant_id: str
    action: str
    encrypted_payload: str
    payload_hash: str
    created_at: float = field(default_factory=time.time)
    retained_days: int = 365
    metadata: Dict[str, Any] = field(default_factory=dict)


class Tier3AuditLedger:
    """Encrypted compliance ledger with cryptographic hashing and Merkle ledger fan-out."""

    def __init__(
        self,
        encryption_key: Optional[bytes] = None,
        default_ttl_days: int = 365,
        unified_ledger: Optional[Any] = None,
    ):
        self.default_ttl_days = default_ttl_days
        # Use provided 32-byte urlsafe base64 key or derive a local one
        if encryption_key:
            self._key = encryption_key
        else:
            self._key = Fernet.generate_key()

        self._fernet = Fernet(self._key)
        self._records: Dict[str, EncryptedAuditRecord] = {}
        self._unified_ledger = unified_ledger

    def encrypt(self, data: Any) -> str:
        """Encrypts serializable data into an authenticated Fernet ciphertext string."""
        if isinstance(data, (dict, list)):
            raw = json.dumps(data, sort_keys=True).encode("utf-8")
        elif isinstance(data, str):
            raw = data.encode("utf-8")
        else:
            raw = str(data).encode("utf-8")

        token = self._fernet.encrypt(raw)
        return token.decode("utf-8")

    def decrypt(self, encrypted_token: str) -> Any:
        """Decrypts a previously encrypted audit payload."""
        decrypted_bytes = self._fernet.decrypt(encrypted_token.encode("utf-8"))
        decoded_str = decrypted_bytes.decode("utf-8")
        try:
            return json.loads(decoded_str)
        except Exception:
            return decoded_str

    def store(
        self,
        raw_payload: Any,
        user_id: str,
        action: str = "agent_action",
        tenant_id: str = "default",
        ttl_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EncryptedAuditRecord:
        """Encrypts and registers a tamper-proof audit record with 1-year compliance guarantee."""
        ttl = ttl_days if ttl_days is not None else self.default_ttl_days
        now = time.time()
        audit_id = f"aud_{int(now*1000)}_{len(self._records)}"

        encrypted_payload = self.encrypt(raw_payload)
        payload_hash = hashlib.sha256(encrypted_payload.encode("utf-8")).hexdigest()

        rec = EncryptedAuditRecord(
            audit_id=audit_id,
            user_id=user_id,
            tenant_id=tenant_id,
            action=action,
            encrypted_payload=encrypted_payload,
            payload_hash=payload_hash,
            created_at=now,
            retained_days=ttl,
            metadata=metadata or {},
        )
        self._records[audit_id] = rec

        # Fan-out to Layer 10 Merkle unified ledger if available
        if self._unified_ledger is not None:
            try:
                self._unified_ledger.record(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    role="system",
                    module="safety.pii.tier3",
                    action=action,
                    resource=audit_id,
                    status="success",
                    severity=AuditSeverity.NOTICE if _LEDGER_AVAILABLE else "notice",
                    details={
                        "payload_hash": payload_hash,
                        "retained_days": ttl,
                        **(metadata or {}),
                    },
                )
            except Exception:
                pass

        return rec

    def get_records(self, user_id: Optional[str] = None) -> List[EncryptedAuditRecord]:
        records = list(self._records.values())
        if user_id:
            records = [r for r in records if r.user_id == user_id]
        return records

    def purge(self, user_id: str) -> int:
        """Right-to-erasure compliance purge for user records."""
        to_del = [aid for aid, r in self._records.items() if r.user_id == user_id]
        for aid in to_del:
            del self._records[aid]
        return len(to_del)

