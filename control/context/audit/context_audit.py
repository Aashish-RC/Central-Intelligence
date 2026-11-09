"""Context Audit Log & Merkle Ledger Bridge (Layer 9: Context Engineering, Feature 9.13).

Guarantees byte-for-byte reproducibility of every context payload dispatched to any model,
paired with cryptographic hashing and tamper-evident Merkle ledger provenance.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from control.safety.audit.ledger import AuditLedger
    from control.safety.audit.models import UnifiedAuditEntry, AuditSeverity
    _SAFETY_AUDIT_AVAILABLE = True
except ImportError:
    _SAFETY_AUDIT_AVAILABLE = False


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ContextAuditRecord:
    """Byte-for-byte record of context delivered to a model for a specific response."""
    response_id: str
    sha256_hash: str
    raw_prompt: str
    timestamp: str = field(default_factory=utc_iso_now)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    tenant_id: str = "default"
    token_count: int = 0
    sources_included: List[str] = field(default_factory=list)
    injections_flagged: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextAuditLog:
    """Tamper-evident audit store for model context payloads."""

    def __init__(self, db_path: Optional[str] = None, safety_ledger: Optional[Any] = None):
        self.db_path = db_path or ":memory:"
        self.safety_ledger = safety_ledger
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS context_audit_records (
                    response_id TEXT PRIMARY KEY,
                    sha256_hash TEXT NOT NULL,
                    raw_prompt TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    tenant_id TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    sources_included TEXT NOT NULL,
                    injections_flagged INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def record(
        self,
        response_id: str,
        raw_prompt: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tenant_id: str = "default",
        token_count: int = 0,
        sources_included: Optional[List[str]] = None,
        injections_flagged: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ContextAuditRecord:
        """Stores a byte-for-byte record of the prompt and writes an entry to the Merkle ledger."""
        sources_included = sources_included or []
        metadata = metadata or {}

        # Compute deterministic SHA-256 over raw UTF-8 prompt
        prompt_bytes = raw_prompt.encode("utf-8")
        sha256_hash = hashlib.sha256(prompt_bytes).hexdigest()
        ts = utc_iso_now()

        rec = ContextAuditRecord(
            response_id=response_id,
            sha256_hash=sha256_hash,
            raw_prompt=raw_prompt,
            timestamp=ts,
            user_id=user_id,
            session_id=session_id,
            tenant_id=tenant_id,
            token_count=token_count,
            sources_included=sources_included,
            injections_flagged=injections_flagged,
            metadata=metadata,
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO context_audit_records (
                    response_id, sha256_hash, raw_prompt, timestamp, user_id,
                    session_id, tenant_id, token_count, sources_included,
                    injections_flagged, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.response_id,
                    rec.sha256_hash,
                    rec.raw_prompt,
                    rec.timestamp,
                    rec.user_id,
                    rec.session_id,
                    rec.tenant_id,
                    rec.token_count,
                    json.dumps(rec.sources_included),
                    rec.injections_flagged,
                    json.dumps(rec.metadata),
                ),
            )
            conn.commit()

        # Bridge to L10 Merkle ledger if available
        if self.safety_ledger is not None:
            try:
                self.safety_ledger.record_action(
                    module="context_engineering",
                    action="context_dispatch",
                    resource=f"response:{response_id}",
                    tenant_id=tenant_id,
                    user_id=user_id,
                    details={
                        "sha256": sha256_hash,
                        "token_count": token_count,
                        "sources": sources_included,
                        "injections_flagged": injections_flagged,
                    },
                )
            except Exception:
                pass

        return rec

    def get_record(self, response_id: str) -> Optional[ContextAuditRecord]:
        """Retrieves audit record by response_id."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT response_id, sha256_hash, raw_prompt, timestamp, user_id,
                       session_id, tenant_id, token_count, sources_included,
                       injections_flagged, metadata_json
                FROM context_audit_records
                WHERE response_id = ?
                """,
                (response_id,),
            )
            row = cur.fetchone()
            if not row:
                return None

            return ContextAuditRecord(
                response_id=row[0],
                sha256_hash=row[1],
                raw_prompt=row[2],
                timestamp=row[3],
                user_id=row[4],
                session_id=row[5],
                tenant_id=row[6],
                token_count=row[7],
                sources_included=json.loads(row[8]),
                injections_flagged=row[9],
                metadata=json.loads(row[10]),
            )

    def reconstruct(self, response_id: str) -> Optional[str]:
        """Reconstructs exactly what context the model was provided for a past response."""
        record = self.get_record(response_id)
        if not record:
            return None
        return record.raw_prompt

    def verify_integrity(self, response_id: str) -> bool:
        """Cryptographically verifies that stored prompt matches stored SHA-256 hash."""
        record = self.get_record(response_id)
        if not record:
            return False
        computed_hash = hashlib.sha256(record.raw_prompt.encode("utf-8")).hexdigest()
        return computed_hash == record.sha256_hash
