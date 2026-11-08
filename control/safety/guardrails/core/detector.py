"""
Pheonix PII & Content Sanitization Detector
Scans and redacts sensitive personally identifiable information (PII) and secret tokens.
"""

import re
from typing import Tuple, List

PII_PATTERNS = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")),
    ("SECRET_KEY", re.compile(r"\b(?:sk-[a-zA-Z0-9_-]{20,}|ghp_[a-zA-Z0-9]{20,}|xox[baprs]-[a-zA-Z0-9]{10,}|AKIA[0-9A-Z]{16})\b")),
    ("PHONE", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
]


class PIIDetector:
    """Scans and sanitizes sensitive user information from prompt payloads."""

    def sanitize(self, text: str) -> Tuple[str, bool, List[str]]:
        """
        Redacts PII tokens from text.
        Returns (sanitized_text, was_redacted, matched_types).
        """
        sanitized = text
        matched_types = []

        for pii_type, regex in PII_PATTERNS:
            if regex.search(sanitized):
                matched_types.append(pii_type)
                sanitized = regex.sub(f"[REDACTED_{pii_type}]", sanitized)

        return sanitized, len(matched_types) > 0, matched_types
