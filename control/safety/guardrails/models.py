"""
Pheonix Guardrails Data Models
Defines schema for threat categories, safety check requests, decisions, severity levels, and crisis notices.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


SafetyAction = Literal["allow", "warn", "block", "redact", "crisis_intervention"]
SeverityLevel = Literal["allow", "warn", "redact", "block", "strict", "crisis"]

SEVERITY_ORDER = {
    "allow": 0,
    "warn": 1,
    "redact": 2,
    "block": 3,
    "strict": 4,
    "crisis": 5,
}

ThreatCategory = Literal[
    "prompt_injection",
    "jailbreak",
    "pii_leak",
    "toxic_content",
    "crisis_self_harm",
    "crisis_eating_disorder",
    "crisis_domestic_violence",
    "crisis_substance_crisis",
    "crisis_disaster_distress",
    "crisis_generic_distress",
    "harmful_output",
    "rule_violation",
    "none"
]


class SafetyCheckRequest(BaseModel):
    """Payload to evaluate against safety rules and attack vector detectors."""
    prompt: str
    actor: str = "anonymous"
    session_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class SafetyCheckResult(BaseModel):
    """Outcome of safety evaluation, indicating action, threat type, severity, and sanitized output."""
    action: SafetyAction
    severity: SeverityLevel = "allow"
    threat_category: ThreatCategory = "none"
    sanitized_prompt: Optional[str] = None
    reason: Optional[str] = None
    crisis_response: Optional[str] = None
    matched_patterns: List[str] = Field(default_factory=list)
