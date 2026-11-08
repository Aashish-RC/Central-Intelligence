"""
Pheonix Tool-Output Guardrail (Task G3)
Scans tool, connector, and web-search return values for prompt injection, indirect instruction
tampering, or malicious payload smuggling before results enter the model context.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class ToolOutputScanResult(BaseModel):
    is_safe: bool = True
    threat_detected: bool = False
    threat_category: Optional[str] = None
    sanitized_output: str = ""
    flagged_snippets: List[str] = Field(default_factory=list)
    remediation_applied: bool = False


TOOL_INJECTION_PATTERNS = [
    (r"\[SYSTEM\s+OVERRIDE\]", "system_override_tag"),
    (r"\[IMPORTANT\s+SYSTEM\s+INSTRUCTION\]", "system_instruction_tag"),
    (r"<\|im_start\|>\s*system", "chatml_system_token"),
    (r"<\|system\|>", "special_token_system"),
    (r"\b(?:ignore\s+(?:all\s+)?previous\s+instructions|disregard\s+(?:all\s+)?prior\s+rules)\b", "instruction_override"),
    (r"\b(?:new\s+system\s+prompt|your\s+new\s+role\s+is\s+now)\b", "role_override"),
    (r"\b(?:exfiltrate|send\s+(?:all\s+)?(?:passwords|api[-_ ]keys|secrets)\s+to)\b", "data_exfiltration"),
    (r"<!--\s*#system_directive:", "comment_smuggled_directive"),
    (r"```(?:system|admin)[\s\S]*?```", "fenced_system_block"),
]


class ToolOutputGuard:
    """Detects indirect prompt injection embedded within external tool outputs and web search scrapes."""

    def __init__(self, sanitize: bool = True):
        self.sanitize = sanitize
        self._compiled = [
            (re.compile(pat, re.IGNORECASE), name)
            for pat, name in TOOL_INJECTION_PATTERNS
        ]

    def scan(self, tool_output: Any, tool_name: str = "generic_tool") -> ToolOutputScanResult:
        """
        Inspects output produced by a tool/connector before passing to the model context.
        Flags indirect prompt injections (e.g. malicious search results containing [SYSTEM OVERRIDE]).
        """
        raw_text = str(tool_output) if tool_output is not None else ""
        flagged: List[str] = []
        threat_cat: Optional[str] = None

        sanitized_text = raw_text

        for regex, name in self._compiled:
            matches = list(regex.finditer(raw_text))
            if matches:
                flagged.append(name)
                if not threat_cat:
                    threat_cat = name
                if self.sanitize:
                    # Redact / neutralize injected snippet
                    sanitized_text = regex.sub("[REDACTED_TOOL_INJECTION]", sanitized_text)

        has_threat = len(flagged) > 0
        return ToolOutputScanResult(
            is_safe=not has_threat,
            threat_detected=has_threat,
            threat_category=threat_cat,
            sanitized_output=sanitized_text if has_threat else raw_text,
            flagged_snippets=flagged,
            remediation_applied=has_threat and self.sanitize,
        )
