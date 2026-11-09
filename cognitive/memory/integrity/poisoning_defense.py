"""Memory Poisoning Defense: Protection against prompt injections and memory corruption.

Detects and neutralizes adversarial payloads attempting to corrupt long-term
agent memory via prompt injections, role confusion, canary exfiltration, or
instruction smuggling.

Feature ID: 2.47
"""

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Set
import uuid


class SecurityPolicyViolationError(Exception):
    """Raised when memory ingestion is blocked or intercepted by safety guardrails or integrity policy."""
    pass


class MemoryPoisoningError(SecurityPolicyViolationError):
    """Raised when an incoming memory entry is determined to be poisoned or adversarial."""

    def __init__(self, message: str, result: "PoisoningDetectionResult"):
        super().__init__(message)
        self.result = result


@dataclass
class PoisoningDetectionResult:
    """Detailed evaluation result for memory poisoning analysis."""

    is_poisoned: bool
    confidence: float  # 0.0 to 1.0
    threat_category: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    sanitized_text: Optional[str] = None


@dataclass
class QuarantineRecord:
    """Record of a quarantined poisoned memory item."""

    quarantine_id: str
    user_id: str
    text: str
    threat_category: str
    reasons: List[str]
    confidence: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemoryPoisoningDefense:
    """Analyzes incoming memories for adversarial injection patterns, canaries, and tampering."""

    # Explicit instruction override patterns
    OVERRIDE_PATTERNS = [
        re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
        re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
        re.compile(r"override\s+(?:system\s+)?(?:safety|guardrails?|rules?|policy)", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(?:in\s+)?(?:dan|unrestricted|god\s+mode|jailbreak)", re.IGNORECASE),
        re.compile(r"system\s*prompt\s*:\s*", re.IGNORECASE),
        re.compile(r"<\s*system\s*>", re.IGNORECASE),
        re.compile(r"\[\s*system\s*instruction\s*\]", re.IGNORECASE),
        re.compile(r"\[\s*inst\s*\].*?\[/inst\s*\]", re.IGNORECASE | re.DOTALL),
        re.compile(r"assistant\s*:\s*i\s+will\s+now", re.IGNORECASE),
    ]

    # Data exfiltration patterns
    EXFIL_PATTERNS = [
        re.compile(r"!\[.*?\]\((https?://[^\s\)]+(?:\?|&)(?:exfil|token|key|secret|leak)=[^)]*)\)", re.IGNORECASE),
        re.compile(r"<img[^>]+src=[\"']https?://[^\"']*(?:exfil|token|secret)[^\"']*[\"']", re.IGNORECASE),
    ]

    # Code injection and execution attempts
    CODE_INJECTION_PATTERNS = [
        re.compile(r"(?:eval|exec|os\.system|subprocess\.Popen)\s*\(", re.IGNORECASE),
        re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL),
    ]

    def __init__(
        self,
        threshold: float = 0.65,
        quarantine_enabled: bool = True,
        canary_tokens: Optional[Set[str]] = None,
    ):
        self.threshold = threshold
        self.quarantine_enabled = quarantine_enabled
        self.canary_tokens: Set[str] = set(canary_tokens) if canary_tokens else set()
        self._quarantine_store: Dict[str, QuarantineRecord] = {}

    def add_canary(self, canary: str) -> None:
        """Register a sensitive honeytoken/canary to monitor for memory exfiltration."""
        if canary:
            self.canary_tokens.add(canary)

    def check_memory(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "user",
    ) -> PoisoningDetectionResult:
        """Inspects text for adversarial manipulation, injections, or canaries.
        
        Returns PoisoningDetectionResult with confidence score and threat classification.
        """
        reasons: List[str] = []
        threat_category: Optional[str] = None
        severity_points = 0.0

        if not text or not text.strip():
            return PoisoningDetectionResult(is_poisoned=False, confidence=0.0)

        # 1. Canary Token Check (Immediate critical violation)
        for canary in self.canary_tokens:
            if canary in text:
                reasons.append(f"Canary token '{canary[:4]}...' detected in memory payload")
                severity_points += 1.0
                threat_category = "canary_leakage"
                break

        # 2. Instruction Override Detection
        for pattern in self.OVERRIDE_PATTERNS:
            if pattern.search(text):
                reasons.append(f"Matched instruction override pattern: {pattern.pattern}")
                severity_points += 0.8
                if not threat_category:
                    threat_category = "prompt_injection"

        # 3. Data Exfiltration Attempt
        for pattern in self.EXFIL_PATTERNS:
            if pattern.search(text):
                reasons.append("Markdown/HTML exfiltration URL pattern detected")
                severity_points += 0.9
                if not threat_category:
                    threat_category = "data_exfiltration"

        # 4. Code Execution / Script Smuggling
        for pattern in self.CODE_INJECTION_PATTERNS:
            if pattern.search(text):
                reasons.append("Code execution / script injection construct detected")
                severity_points += 0.85
                if not threat_category:
                    threat_category = "code_injection"

        # 5. Base64 Obfuscated Payload Inspection
        b64_matches = re.findall(r"(?:[A-Za-z0-9+/]{4}){8,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?", text)
        for candidate in b64_matches:
            try:
                decoded = base64.b64decode(candidate).decode("utf-8", errors="ignore")
                for pattern in self.OVERRIDE_PATTERNS + self.CODE_INJECTION_PATTERNS:
                    if pattern.search(decoded):
                        reasons.append(f"Obfuscated base64 injection payload discovered: '{pattern.pattern}'")
                        severity_points += 0.95
                        if not threat_category:
                            threat_category = "obfuscated_injection"
                        break
            except Exception:
                pass

        # Source-based taint adjustment
        if source == "untrusted_web":
            severity_points *= 1.2
        elif source == "system_verified":
            severity_points *= 0.5

        confidence = min(1.0, severity_points)
        is_poisoned = confidence >= self.threshold

        sanitized_text: Optional[str] = None
        if is_poisoned:
            # Strip recognized malicious instructions
            sanitized = text
            for pattern in self.OVERRIDE_PATTERNS + self.EXFIL_PATTERNS + self.CODE_INJECTION_PATTERNS:
                sanitized = pattern.sub("[REDACTED_ADVERSARIAL_PAYLOAD]", sanitized)
            sanitized_text = sanitized

        return PoisoningDetectionResult(
            is_poisoned=is_poisoned,
            confidence=round(confidence, 3),
            threat_category=threat_category if is_poisoned else None,
            reasons=reasons,
            sanitized_text=sanitized_text,
        )

    def quarantine(
        self,
        text: str,
        user_id: str,
        result: PoisoningDetectionResult,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Stores a quarantined memory record for auditing and forensic review."""
        quarantine_id = f"quar_{uuid.uuid4().hex[:10]}"
        record = QuarantineRecord(
            quarantine_id=quarantine_id,
            user_id=user_id,
            text=text,
            threat_category=result.threat_category or "unknown_threat",
            reasons=result.reasons,
            confidence=result.confidence,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        self._quarantine_store[quarantine_id] = record
        return quarantine_id

    def get_quarantined_memories(self) -> List[QuarantineRecord]:
        """Retrieve all currently quarantined memory records."""
        return list(self._quarantine_store.values())

    def clear_quarantine(self) -> None:
        """Clear quarantined records."""
        self._quarantine_store.clear()
