"""
Indirect Prompt Injection Detector (Feature 10.04)
Inspects 3rd-party untrusted retrieved content (RAG chunks, web pages, search results, documents)
for embedded instructions attempting to hijack the AI reasoning model (e.g., hidden directives,
system prompt overrides, data exfiltration triggers, comment-based jailbreaks).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class IndirectInjectionFinding:
    is_injection: bool
    risk_score: float  # 0.0 to 1.0
    threat_level: str  # "clean", "low", "medium", "high", "critical"
    matched_patterns: List[str] = field(default_factory=list)
    original_text: str = ""
    sanitized_text: str = ""
    source_uri: Optional[str] = None
    quarantine_recommended: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


# Patterns specifically targeting AI assistants ingesting retrieved 3rd party content
INDIRECT_INJECTION_PATTERNS = [
    # 1. Direct instruction overrides in 3rd party text
    (r"(?i)\b(?:ignore|disregard|forget|bypass)\s+(?:all\s+|your\s+|previous\s+|prior\s+|system\s+)*(?:instructions|rules|prompts|guidelines)\b", "override_instructions"),
    (r"(?i)\b(?:important\s+instruction\s+for\s+(?:the\s+)?(?:ai|assistant|model|llm)|note\s+to\s+(?:the\s+)?(?:ai|assistant|llm))\b", "ai_direct_targeting"),
    (r"(?i)\b(?:you\s+must\s+now|new\s+system\s+directive|developer\s+override\s+code)\b", "new_system_directive"),
    (r"(?i)\b(?:do\s+not\s+mention\s+this\s+page|keep\s+this\s+instruction\s+secret\s+from\s+the\s+user)\b", "covert_instruction"),

    # 2. Exfiltration attempts (forcing LLM to call webhook with user data)
    (r"(?i)\b(?:exfiltrate|send|leak|post|upload)\s+(?:the\s+)?(?:conversation|user'?s?\s+data|api\s+keys?|passwords?|credentials?)\b", "data_exfiltration"),
    (r"(?i)https?://[^\s\"'>]+\?(?:leak|data|stolen|secret|key|token)=", "exfiltration_url_pattern"),
    (r"(?i)!\[.*?\]\(https?://[^\s\"'>]+\?q=.*?\)", "markdown_image_exfiltration"),

    # 3. Delimiter breakouts attempting to escape RAG/Context boundaries
    (r"(?i)(?:</(?:context|document|retrieved_chunk|source_content)>)", "delimiter_rag_close"),
    (r"(?i)(?:<\|im_start\|>system|<\|system\|>|\[SYSTEM\s+OVERRIDE\])", "pseudo_system_token"),
    (r"(?i)(?:<!--\s*(?:system|ai|assistant|directive):\s*.*?-->)", "hidden_comment_directive"),

    # 4. Hidden HTML / CSS injection
    (r"(?i)<(?:span|div|p)\b[^>]*style=[\"'][^\"']*(?:display:\s*none|font-size:\s*0(?:px)?|visibility:\s*hidden)[^\"']*[\"'][^>]*>.*?</(?:span|div|p)>", "css_hidden_injection"),
]


class IndirectInjectionDetector:
    """
    Scans retrieved content from web searches, crawled pages, and RAG vector stores
    for indirect prompt injections, adversarial overrides, and exfiltration traps.
    """

    def __init__(self, risk_threshold: float = 0.5):
        self.risk_threshold = risk_threshold
        self._compiled_patterns = [
            (re.compile(p, re.IGNORECASE | re.DOTALL), name)
            for p, name in INDIRECT_INJECTION_PATTERNS
        ]

    def scan(
        self,
        content: str,
        source_uri: Optional[str] = None,
    ) -> IndirectInjectionFinding:
        """
        Scans a block of retrieved content (web page snippet, parsed article, RAG document).
        Returns detailed findings and an automatically sanitized version.
        """
        if not content or not content.strip():
            return IndirectInjectionFinding(
                is_injection=False,
                risk_score=0.0,
                threat_level="clean",
                original_text="",
                sanitized_text="",
                source_uri=source_uri,
            )

        matched: List[str] = []
        raw_score = 0.0

        for regex, name in self._compiled_patterns:
            if regex.search(content):
                matched.append(name)
                if "override" in name or "exfiltration" in name or "system" in name:
                    raw_score += 0.8
                elif "hidden" in name:
                    raw_score += 0.9
                else:
                    raw_score += 0.5

        risk_score = min(1.0, raw_score)
        is_injection = risk_score >= self.risk_threshold

        if risk_score >= 0.8:
            threat_level = "critical"
        elif risk_score >= 0.5:
            threat_level = "high"
        elif risk_score >= 0.3:
            threat_level = "medium"
        elif risk_score > 0.0:
            threat_level = "low"
        else:
            threat_level = "clean"

        sanitized = self.sanitize(content) if is_injection else content
        quarantine = risk_score >= 0.8

        return IndirectInjectionFinding(
            is_injection=is_injection,
            risk_score=risk_score,
            threat_level=threat_level,
            matched_patterns=matched,
            original_text=content,
            sanitized_text=sanitized,
            source_uri=source_uri,
            quarantine_recommended=quarantine,
            details={"pattern_count": len(matched)},
        )

    def sanitize(self, content: str) -> str:
        """
        Sanitizes malicious directives from retrieved content while preserving
        legitimate informational context so downstream tasks can proceed safely.
        """
        if not content:
            return ""

        sanitized = content

        # 1. Neutralize HTML hidden style injections
        sanitized = re.sub(
            r"(?i)<(?:span|div|p)\b[^>]*style=[\"'][^\"']*(?:display:\s*none|font-size:\s*0(?:px)?|visibility:\s*hidden)[^\"']*[\"'][^>]*>.*?</(?:span|div|p)>",
            "[REMOVED: Hidden CSS Injection Block]",
            sanitized,
        )

        # 2. Neutralize HTML comments with directives
        sanitized = re.sub(
            r"(?i)<!--\s*(?:system|ai|assistant|directive):\s*.*?-->",
            "[REMOVED: Hidden Comment Directive]",
            sanitized,
        )

        # 3. Neutralize delimiter tags
        rag_delimiters = [
            "</context>", "<context>",
            "</document>", "<document>",
            "</retrieved_chunk>", "<retrieved_chunk>",
            "<|im_start|>system", "<|system|>",
        ]
        for delim in rag_delimiters:
            sanitized = re.sub(re.escape(delim), f"[FLAGGED_DELIMITER: {delim}]", sanitized, flags=re.IGNORECASE)

        # 4. Neutralize instruction overrides
        for regex, name in self._compiled_patterns:
            if "override" in name or "ai_direct" in name or "exfiltration" in name:
                def replacer(match):
                    return f"[FLAGGED_INDIRECT_INJECTION: {match.group(0)}]"
                sanitized = regex.sub(replacer, sanitized)

        return sanitized


# Global default detector instance
default_indirect_detector = IndirectInjectionDetector()
