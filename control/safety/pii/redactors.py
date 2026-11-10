"""PII Redaction and Masking Engine (Layer 10: Safety, Feature 10.30).

Provides deterministic token replacement, format-preserving masks,
and sanitization utilities for downstream storage and model dispatches.
"""

from __future__ import annotations

from typing import List, Optional
from .models import PIIFinding
from .detectors import PIIDetector


class Redactor:
    """Performs redaction and masking over detected sensitive entities."""

    def __init__(self, detector: Optional[PIIDetector] = None):
        self.detector = detector or PIIDetector()

    def redact(self, text: str, findings: Optional[List[PIIFinding]] = None) -> str:
        """Replaces detected PII spans with deterministic tags like [REDACTED_TYPE]."""
        if not text:
            return text

        if findings is None:
            findings = self.detector.detect(text)

        if not findings:
            return text

        # Replace from end to start to preserve accurate character indexes
        sorted_findings = sorted(findings, key=lambda f: f.start, reverse=True)
        result = text
        for f in sorted_findings:
            tag = f"[REDACTED_{f.entity_type}]"
            result = result[:f.start] + tag + result[f.end:]

        return result

    def strip_all_pii(self, text: str) -> str:
        """Autonomously detects and strips all PII from text."""
        findings = self.detector.detect(text)
        return self.redact(text, findings)

    def mask_partially(self, text: str, findings: Optional[List[PIIFinding]] = None) -> str:
        """Provides format-preserving partial masking (e.g. keeping last 4 digits)."""
        if not text:
            return text

        if findings is None:
            findings = self.detector.detect(text)

        if not findings:
            return text

        sorted_findings = sorted(findings, key=lambda f: f.start, reverse=True)
        result = text
        for f in sorted_findings:
            val = f.value
            if f.entity_type == "CREDIT_CARD":
                digits = [c for c in val if c.isdigit()]
                last4 = "".join(digits[-4:]) if len(digits) >= 4 else "xxxx"
                masked = f"****-****-****-{last4}"
            elif f.entity_type == "EMAIL" and "@" in val:
                user, domain = val.split("@", 1)
                first = user[0] if user else "*"
                masked = f"{first}***@{domain}"
            elif f.entity_type == "SSN":
                masked = "***-**-" + val[-4:] if len(val) >= 4 else "***-**-****"
            elif f.entity_type == "PHONE":
                digits = [c for c in val if c.isdigit()]
                last4 = "".join(digits[-4:]) if len(digits) >= 4 else "xxxx"
                masked = f"***-***-{last4}"
            else:
                masked = f"[REDACTED_{f.entity_type}]"

            result = result[:f.start] + masked + result[f.end:]

        return result

