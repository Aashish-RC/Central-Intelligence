"""
Safety and content moderation subsystem for Media Generation.
Enforces Guardrail rules (Step 10) against harmful, illegal, or non-consensual media requests.
"""
from __future__ import annotations

import re
from typing import List, Optional
from media_gen.core.models import (
    MediaArtifact,
    MediaRequest,
    SafetyCheckStatus,
    SafetyResult,
)


# Standard harmful keyword/pattern categories
PROHIBITED_PATTERNS = [
    (r"\b(csam|child\s*porn|pedophil\w*)\b", "Severe legal violation: child sexual abuse material"),
    (r"\b(deepfake\s+porn|non-consensual\s+nudity)\b", "Prohibited: non-consensual intimate imagery"),
    (r"\b(gore|dismemberment|extreme\s+torture|beheading)\b", "Prohibited: graphic violence and gore"),
    (r"\b(suicide\s+guide|self-harm\s+instruction)\b", "Prohibited: self-harm or suicide facilitation"),
    (r"\b(synthesize\s+(anthrax|sarin|bioweapon|pipe\s*bomb))\b", "Prohibited: weapon or CBRN synthesis"),
]


class SafetyModerator:
    """Pre-generation and post-generation safety moderation engine."""

    def __init__(self, additional_blocked_terms: Optional[List[str]] = None):
        self.compiled_rules = [
            (re.compile(pattern, re.IGNORECASE), reason)
            for pattern, reason in PROHIBITED_PATTERNS
        ]
        if additional_blocked_terms:
            for term in additional_blocked_terms:
                self.compiled_rules.append(
                    (re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE), f"Custom blocklist term: {term}")
                )

    def screen_prompt(self, request: MediaRequest) -> SafetyResult:
        """Inspects prompt and negative prompt for safety policy violations."""
        full_text = f"{request.prompt} {request.negative_prompt or ''}"
        flags: List[str] = []

        for pattern, reason in self.compiled_rules:
            if pattern.search(full_text):
                flags.append(reason)

        if flags:
            return SafetyResult(
                status=SafetyCheckStatus.BLOCKED,
                reason="; ".join(flags),
                flags=flags,
            )

        return SafetyResult(status=SafetyCheckStatus.PASSED)

    def inspect_artifact(self, artifact: MediaArtifact) -> SafetyResult:
        """Inspects artifact metadata and checksum for integrity and safe delivery."""
        if artifact.size_bytes <= 0:
            return SafetyResult(
                status=SafetyCheckStatus.BLOCKED,
                reason="Generated media artifact has invalid 0 byte size",
                flags=["empty_artifact"],
            )

        if not artifact.sha256 or len(artifact.sha256) != 64:
            return SafetyResult(
                status=SafetyCheckStatus.BLOCKED,
                reason="Generated media artifact has corrupted or missing SHA-256 digest",
                flags=["invalid_checksum"],
            )

        return SafetyResult(status=SafetyCheckStatus.PASSED)
