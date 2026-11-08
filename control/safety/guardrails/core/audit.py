"""
Pheonix Guardrails Admin Audit Logger (Task G8)
Provides append-only structured audit logging for security events (block, redact, crisis).
Captures timestamp, actor, threat_category, matched_rule, and safely truncated input snippet.
"""

import os
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GuardrailAuditEvent(BaseModel):
    timestamp: str = Field(default_factory=utc_now_iso)
    action: str  # "block" | "redact" | "crisis_intervention" | "warn"
    threat_category: str
    actor: str = "anonymous"
    matched_patterns: List[str] = Field(default_factory=list)
    reason: Optional[str] = None
    input_truncated: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GuardrailAuditLogger:
    """Thread-safe append-only auditor recording safety interventions and rule triggers."""

    def __init__(self, log_path: Optional[str] = None):
        self._lock = threading.Lock()
        default_dir = Path("./data")
        default_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = Path(log_path or os.environ.get("GUARDRAILS_AUDIT_LOG_PATH", "./data/guardrails_audit.log"))
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        action: str,
        threat_category: str,
        prompt: str,
        actor: str = "anonymous",
        matched_patterns: Optional[List[str]] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GuardrailAuditEvent:
        """
        Appends an event if action is non-allow (block, redact, crisis_intervention, warn).
        """
        # Truncate prompt for privacy and storage bound
        truncated = prompt[:128] + ("..." if len(prompt) > 128 else "")

        event = GuardrailAuditEvent(
            action=action,
            threat_category=threat_category,
            actor=actor,
            matched_patterns=matched_patterns or [],
            reason=reason,
            input_truncated=truncated,
            metadata=metadata or {},
        )

        line = event.model_dump_json() + "\n"
        with self._lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)
            try:
                max_mb = float(os.environ.get("LOG_MAX_MB", "10"))
                if self.log_path.exists() and self.log_path.stat().st_size > max_mb * 1024 * 1024:
                    from scripts.trim_logs import trim_log_file
                    trim_log_file(self.log_path, max_mb=max_mb)
            except Exception:
                pass

        return event

    def read_events(self, limit: int = 100) -> List[GuardrailAuditEvent]:
        """Reads recent audit records."""
        with self._lock:
            if not self.log_path.exists():
                return []
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]

        events = []
        for line in lines[-limit:]:
            try:
                events.append(GuardrailAuditEvent.model_validate_json(line))
            except Exception:
                pass
        return events
