"""High-speed PII Detection Engine (Layer 10: Safety, Feature 10.30).

Extends existing regex & pattern detectors with Luhn verification,
non-overlapping span resolution, and strict API token detection.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set
from .models import PIIFinding


def luhn_checksum(digits: str) -> bool:
    """Verifies standard Luhn checksum algorithm for credit card numbers."""
    if not digits.isdigit():
        return False
    total = 0
    reverse_digits = digits[::-1]
    for i, char in enumerate(reverse_digits):
        n = int(char)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


class PIIDetector:
    """Detects personally identifiable information and secret keys in text."""

    def __init__(self, enabled_types: Optional[Set[str]] = None):
        self.enabled_types = enabled_types or {
            "EMAIL",
            "SSN",
            "CREDIT_CARD",
            "PHONE",
            "SECRET_KEY",
            "IP_ADDRESS",
        }

        self._email_re = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
        self._ssn_re = re.compile(r"\b(?!000|666|9\d{2})(\d{3})-(?!00)(\d{2})-(?!0000)(\d{4})\b")
        self._phone_re = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
        self._secret_key_re = re.compile(
            r"\b(?:sk-(?:proj-)?[A-Za-z0-9_\-]{16,}|ghp_[a-zA-Z0-9]{20,}|xox[baprs]-[a-zA-Z0-9]{10,}|AKIA[0-9A-Z]{16})\b"
        )
        self._ip_re = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        self._cc_candidate_re = re.compile(r"\b(?:\d[ -]?){13,19}\b")
        self._cc_standard_re = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")

    def detect(self, text: str) -> List[PIIFinding]:
        """Scans text and returns non-overlapping PII findings sorted by position."""
        if not text:
            return []

        raw_findings: List[PIIFinding] = []

        # 1. Secret keys
        if "SECRET_KEY" in self.enabled_types:
            for match in self._secret_key_re.finditer(text):
                raw_findings.append(
                    PIIFinding("SECRET_KEY", match.group(0), match.start(), match.end())
                )

        # 2. Email
        if "EMAIL" in self.enabled_types:
            for match in self._email_re.finditer(text):
                raw_findings.append(
                    PIIFinding("EMAIL", match.group(0), match.start(), match.end())
                )

        # 3. SSN
        if "SSN" in self.enabled_types:
            for match in self._ssn_re.finditer(text):
                raw_findings.append(
                    PIIFinding("SSN", match.group(0), match.start(), match.end())
                )

        # 4. Credit Card (standard 4x4 pattern or Luhn-verified 13-19 digits)
        if "CREDIT_CARD" in self.enabled_types:
            for match in self._cc_standard_re.finditer(text):
                raw_findings.append(
                    PIIFinding("CREDIT_CARD", match.group(0), match.start(), match.end())
                )
            for match in self._cc_candidate_re.finditer(text):
                val = match.group(0)
                digits = re.sub(r"\D", "", val)
                if 13 <= len(digits) <= 19 and luhn_checksum(digits):
                    raw_findings.append(
                        PIIFinding("CREDIT_CARD", val, match.start(), match.end())
                    )

        # 5. Phone
        if "PHONE" in self.enabled_types:
            for match in self._phone_re.finditer(text):
                raw_findings.append(
                    PIIFinding("PHONE", match.group(0), match.start(), match.end())
                )

        # 6. IP Address
        if "IP_ADDRESS" in self.enabled_types:
            for match in self._ip_re.finditer(text):
                val = match.group(0)
                octets = val.split(".")
                if all(0 <= int(o) <= 255 for o in octets):
                    raw_findings.append(
                        PIIFinding("IP_ADDRESS", val, match.start(), match.end())
                    )

        # Resolve overlaps: sort by start asc, longer length takes precedence
        raw_findings.sort(key=lambda f: (f.start, -(f.end - f.start)))
        resolved: List[PIIFinding] = []
        last_end = -1
        for finding in raw_findings:
            if finding.start >= last_end:
                resolved.append(finding)
                last_end = finding.end

        return resolved
