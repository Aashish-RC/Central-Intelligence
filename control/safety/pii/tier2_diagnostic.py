"""Tier 2 Diagnostic Store (Layer 10: Safety, Feature 10.30; Layer 14: Observability, Feature 14.19).

Tier 2: Redacted chat snippets (PII automatically scrubbed) stored ephemerally
for engineer triage and context diagnostics. Configurable retention (default 14–30 days).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class DiagnosticRecord:
    record_id: str
    user_id: str
    session_id: Optional[str]
    redacted_content: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    ttl_days: int = 14
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class Tier2DiagnosticStore:
    """Ephemeral storage for scrubbed, non-sensitive diagnostic snippets."""

    def __init__(self, default_ttl_days: int = 14):
        self.default_ttl_days = default_ttl_days
        self._records: Dict[str, DiagnosticRecord] = {}

    def store(
        self,
        redacted_content: str,
        user_id: str,
        session_id: Optional[str] = None,
        ttl_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DiagnosticRecord:
        """Stores a redacted snippet with an absolute expiration deadline."""
        days = ttl_days if ttl_days is not None else self.default_ttl_days
        now = time.time()
        record_id = f"diag_{int(now*1000)}_{len(self._records)}"
        expires_at = now + (days * 86400)

        record = DiagnosticRecord(
            record_id=record_id,
            user_id=user_id,
            session_id=session_id,
            redacted_content=redacted_content,
            created_at=now,
            expires_at=expires_at,
            ttl_days=days,
            metadata=metadata or {},
        )
        self._records[record_id] = record
        return record

    def get_records(self, user_id: Optional[str] = None) -> List[DiagnosticRecord]:
        """Returns non-expired records, optionally filtered by user."""
        self._evict_expired()
        records = list(self._records.values())
        if user_id:
            records = [r for r in records if r.user_id == user_id]
        return records

    def purge(self, user_id: str) -> int:
        """Immediate right-to-erasure purge of all diagnostic records for user."""
        to_del = [rid for rid, r in self._records.items() if r.user_id == user_id]
        for rid in to_del:
            del self._records[rid]
        return len(to_del)

    def _evict_expired(self) -> int:
        """Evicts expired records based on TTL."""
        expired = [rid for rid, r in self._records.items() if r.is_expired()]
        for rid in expired:
            del self._records[rid]
        return len(expired)

    def delete_expired(self, current_time: Optional[float] = None) -> int:
        """Evicts expired records past their TTL."""
        now = current_time if current_time is not None else time.time()
        expired = [
            rid for rid, r in self._records.items()
            if (r.expires_at and now > r.expires_at) or (r.created_at and (now - r.created_at) > (r.ttl_days * 86400))
        ]
        for rid in expired:
            del self._records[rid]
        return len(expired)


