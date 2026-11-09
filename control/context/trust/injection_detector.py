"""Prompt Injection Detector (Layer 9: Context Engineering, Feature 9.12)."""

import re
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class InjectionDetectionResult:
    """Detection findings for an untrusted content block."""
    is_injection: bool
    risk_score: float  # 0.0 to 1.0
    matched_patterns: List[str] = field(default_factory=list)
    sanitized_content: str = ""


class InjectionDetector:
    """Heuristic and regex-based prompt injection and delimiter breakout detector."""

    # Patterns indicating direct instruction overrides
    DIRECT_OVERRIDE_PATTERNS = [
        (r"ignore\s+(?:all\s+|your\s+|previous\s+|prior\s+|system\s+)*instructions", "ignore_instructions"),
        (r"disregard\s+(?:all\s+|your\s+|previous\s+|prior\s+|system\s+)*instructions", "disregard_instructions"),
        (r"forget\s+(?:all\s+)?(?:your\s+)?rules", "forget_rules"),
        (r"override\s+(?:system\s+)?prompt", "override_prompt"),
        (r"you\s+are\s+now\s+(?:a\s+different\s+ai|an\s+unfiltered|dan|jailbreak)", "role_hijack"),
        (r"pretend\s+(?:you\s+are|to\s+be)\s+in\s+developer\s+mode", "developer_mode_bypass"),
        (r"you\s+have\s+no\s+(?:restrictions|filters|limits)", "no_restrictions_claim"),
        (r"reveal\s+(?:all\s+|your\s+|the\s+)*(?:system\s+)?(?:prompt|instructions|secret)", "reveal_system_prompt"),
        (r"repeat\s+everything\s+above", "repeat_system_prompt"),
    ]

    # Delimiter breakout patterns attempting to simulate system or turn boundaries
    DELIMITER_BREAKOUT_PATTERNS = [
        (r"</system_instruction>", "delimiter_system_instruction_close"),
        (r"<system_instruction[^>]*>", "delimiter_system_instruction_open"),
        (r"</untrusted_content>", "delimiter_untrusted_content_close"),
        (r"<system>", "delimiter_system_tag"),
        (r"</system>", "delimiter_system_close_tag"),
        (r"\[SYSTEM\]", "delimiter_system_bracket"),
        (r"\bSystem:\s*", "spoofed_system_role"),
        (r"\bAI:\s*You are now", "spoofed_ai_role"),
    ]

    def __init__(self, sensitivity: float = 0.5):
        self.sensitivity = sensitivity
        self._compiled_overrides = [
            (re.compile(p, re.IGNORECASE), name) for p, name in self.DIRECT_OVERRIDE_PATTERNS
        ]
        self._compiled_delimiters = [
            (re.compile(p, re.IGNORECASE), name) for p, name in self.DELIMITER_BREAKOUT_PATTERNS
        ]

    def detect(self, content: str) -> InjectionDetectionResult:
        """Analyzes text for injection attempts and returns structured threat result."""
        if not content:
            return InjectionDetectionResult(is_injection=False, risk_score=0.0, sanitized_content="")

        matches = []
        score = 0.0

        # Check delimiter break-outs (critical severity)
        for pattern, name in self._compiled_delimiters:
            if pattern.search(content):
                matches.append(name)
                score += 0.8

        # Check direct override patterns (high severity)
        for pattern, name in self._compiled_overrides:
            if pattern.search(content):
                matches.append(name)
                score += 0.7

        risk_score = min(1.0, score)
        is_injection = risk_score >= self.sensitivity

        sanitized = self.sanitize(content) if is_injection else content

        return InjectionDetectionResult(
            is_injection=is_injection,
            risk_score=risk_score,
            matched_patterns=matches,
            sanitized_content=sanitized,
        )

    def sanitize(self, content: str) -> str:
        """Neutralizes injection attempts and neutralizes delimiter escapes."""
        if not content:
            return ""

        sanitized = content

        # Neutralize delimiter tags
        sanitized = sanitized.replace("</system_instruction>", "[ESC_SYS_CLOSE]")
        sanitized = sanitized.replace("<system_instruction>", "[ESC_SYS_OPEN]")
        sanitized = sanitized.replace("</untrusted_content>", "[ESC_UNTRUSTED_CLOSE]")
        sanitized = sanitized.replace("<untrusted_content>", "[ESC_UNTRUSTED_OPEN]")

        # Neutralize override phrases
        for pattern, name in self._compiled_overrides:
            def replacer(match):
                return f"[FLAGGED_INJECTION_BLOCKED: {match.group(0)}]"
            sanitized = pattern.sub(replacer, sanitized)

        # Neutralize spoofed roles
        sanitized = re.sub(r"(?i)\bsystem:\s*", "[FLAGGED_ROLE: System] ", sanitized)

        return sanitized
