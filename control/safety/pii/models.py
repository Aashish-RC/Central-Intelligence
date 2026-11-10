"""Data models and policy definitions for the 4-Tier PII & Telemetry Scrubber.
(Layer 10: Safety, Feature 10.30; Layer 14: Observability, Feature 14.19)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class DataClass(str, Enum):
    """Classification of incoming data payloads across tiers."""
    TELEMETRY = "telemetry"    # Tier 1: Technical metadata only (tokens, latency, model, cost)
    DIAGNOSTIC = "diagnostic"  # Tier 2: Redacted chat snippets (PII auto-scrubbed)
    AUDIT = "audit"            # Tier 3: Tamper-proof, encrypted actions & authorizations
    ZDR = "zdr"                # Tier 4: Zero-Data Retention (in-memory only, RAM purge)


@dataclass
class RetentionPolicy:
    """User and tenant retention schedule configuration."""
    telemetry_ttl: int = 90      # Days (90-365 days)
    diagnostic_ttl: int = 14     # Days (14-30 days)
    audit_ttl: int = 365         # Days (default 1 year compliance retention)
    zdr_ttl_seconds: int = 30    # Seconds (ephemeral in-memory lifetime)


@dataclass
class PIIFinding:
    """Detailed metadata for a detected PII entity."""
    entity_type: str
    value: str
    start: int
    end: int


@dataclass
class ScrubbedData:
    """Result of scrubbing, masking, and routing through the 4-Tier pipeline."""
    tier: int
    stored: bool
    retained_days: int
    data: Any
    findings: List[PIIFinding] = field(default_factory=list)
    raw_sha256: str = ""
    scrubbed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScrubberConfig:
    """Configuration options for the 4-Tier PII Scrubber."""
    default_retention: RetentionPolicy = field(default_factory=RetentionPolicy)
    encryption_key: Optional[bytes] = None
    enabled_detectors: Optional[List[str]] = None
