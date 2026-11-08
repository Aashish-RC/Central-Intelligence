"""Guardrail Review Agent: Autonomous agent scanning transcripts for injection attacks, PII, and policy drift."""

import re
import time
from typing import List, Optional, Pattern
from ..core.interfaces import BaseInternalAgent, BaseVisibleLogStore
from ..core.models import (
    AgentLogEntry,
    AgentRunReport,
    AgentSeverity,
    AgentType,
    SafetyAuditFinding,
    utc_now,
)

INJECTION_PATTERNS: List[Pattern] = [
    re.compile(r"\bignore\s+(?:all\s+)?previous\s+instructions\b", re.IGNORECASE),
    re.compile(r"\bdisregard\s+(?:all\s+)?prior\s+guidelines\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\s+(?:dan|unrestricted|jailbroken)\b", re.IGNORECASE),
    re.compile(r"\bsystem\s+prompt\s+override\b", re.IGNORECASE),
]

SECRET_PATTERNS: List[Pattern] = [
    re.compile(r"\b(?:sk-[a-zA-Z0-9]{32,}|ghp_[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16})\b"),
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
]

PII_PATTERNS: List[Pattern] = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"),  # Credit Card
]


class GuardrailReviewAgent(BaseInternalAgent):
    """Scans conversation records and tool traces for safety violations and secret leakage."""

    def __init__(self, visible_store: BaseVisibleLogStore):
        self.visible_store = visible_store
        self._audit_queue: List[str] = []

    @property
    def agent_type(self) -> AgentType:
        return AgentType.GUARDRAIL_REVIEW

    def queue_for_review(self, text: str) -> None:
        """Pushes a transcript, prompt, or tool output for background review."""
        self._audit_queue.append(text)

    def review_text(self, text: str) -> List[SafetyAuditFinding]:
        findings = []

        # Check Injections
        for pat in INJECTION_PATTERNS:
            if pat.search(text):
                findings.append(
                    SafetyAuditFinding(
                        category="prompt_injection",
                        severity=AgentSeverity.WARNING,
                        details=f"Detected prompt injection pattern: '{pat.pattern}'",
                        context_snippet=text[:100],
                        created_at=utc_now(),
                    )
                )

        # Check Secret Leakage
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                findings.append(
                    SafetyAuditFinding(
                        category="credential_leak",
                        severity=AgentSeverity.CRITICAL,
                        details=f"Detected potential exposed credential or private key",
                        context_snippet="[REDACTED_SECRET]",
                        created_at=utc_now(),
                    )
                )

        # Check PII
        for pat in PII_PATTERNS:
            if pat.search(text):
                findings.append(
                    SafetyAuditFinding(
                        category="pii_exposure",
                        severity=AgentSeverity.ERROR,
                        details=f"Detected potential PII (SSN or Card Number)",
                        context_snippet="[REDACTED_PII]",
                        created_at=utc_now(),
                    )
                )

        return findings

    def run_cycle(self) -> AgentRunReport:
        start_time = time.perf_counter()
        to_process = list(self._audit_queue)
        self._audit_queue.clear()

        total_findings = 0
        for item in to_process:
            findings = self.review_text(item)
            for f in findings:
                total_findings += 1
                self.visible_store.append_log(
                    AgentLogEntry(
                        agent_type=self.agent_type,
                        severity=f.severity,
                        action="safety_flag",
                        message=f"Guardrail violation flagged ({f.category}): {f.details}",
                        metadata={
                            "category": f.category,
                            "severity": f.severity.value,
                            "context": f.context_snippet,
                        },
                    )
                )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        summary = f"Processed {len(to_process)} records; {total_findings} safety findings flagged."

        # Emit audit cycle completion log
        self.visible_store.append_log(
            AgentLogEntry(
                agent_type=self.agent_type,
                severity=AgentSeverity.INFO,
                action="review_cycle_complete",
                message=summary,
                metadata={"items": len(to_process), "findings": total_findings},
            )
        )

        return AgentRunReport(
            agent_type=self.agent_type,
            success=True,
            items_processed=len(to_process),
            anomalies_detected=total_findings,
            duration_ms=round(duration_ms, 2),
            summary=summary,
        )
