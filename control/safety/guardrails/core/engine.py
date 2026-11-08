"""
Pheonix Guardrails Engine
Orchestrates multi-layer safety evaluation (Crisis, Jailbreak/Injection, PII Sanitization),
configurable severity thresholds (G7), and security audit logging (G8).
"""

import os
from typing import Optional, Literal, Dict, List, Tuple, Any, cast
from ..models import (
    SafetyAction,
    SafetyCheckRequest,
    SafetyCheckResult,
    SeverityLevel,
    ThreatCategory,
    SEVERITY_ORDER,
)
from .crisis import CrisisHandler
from .jailbreak import JailbreakDetector
from .detector import PIIDetector
from .audit import GuardrailAuditLogger


class GuardrailsEngine:
    """
    Central safety and guardrails evaluation engine for Pheonix.
    Configurable severity thresholds: lower environments or strict deployments can enforce stricter boundaries.
    """

    def __init__(
        self,
        crisis_handler: Optional[CrisisHandler] = None,
        jailbreak_detector: Optional[JailbreakDetector] = None,
        pii_detector: Optional[PIIDetector] = None,
        audit_logger: Optional[GuardrailAuditLogger] = None,
        severity_threshold: Optional[SeverityLevel] = None,
        rules_client: Optional[Any] = None,
    ):
        self.crisis_handler = crisis_handler or CrisisHandler()
        self.jailbreak_detector = jailbreak_detector or JailbreakDetector()
        self.pii_detector = pii_detector or PIIDetector()
        self.audit_logger = audit_logger or GuardrailAuditLogger()
        self._compiled_rule_patterns: Dict[str, Any] = {}
        self.rules_client = None

        env_threshold = os.environ.get("GUARDRAILS_SEVERITY_THRESHOLD", "warn").lower()
        self.severity_threshold: SeverityLevel = severity_threshold or (
            cast(SeverityLevel, env_threshold) if env_threshold in SEVERITY_ORDER else "warn"
        )

        if rules_client is not None:
            self.attach_rules_client(rules_client)

    def attach_rules_client(self, rules_client: Any) -> None:
        """Wires rules.client event listener and compiles initial rules into runtime regexes/taxonomies."""
        self.rules_client = rules_client
        # Initial compile of cached rules
        if hasattr(rules_client, "_local_rules"):
            for rule in rules_client._local_rules.values():
                self._compile_rule(rule)

        # Subscribe to live push updates if engine supports subscription
        if hasattr(rules_client, "engine") and hasattr(rules_client.engine, "subscribe"):
            try:
                rules_client.engine.subscribe(
                    subscriber_id=f"guardrails_engine_{id(self)}",
                    callback=self._on_rule_change,
                    scope_filter=getattr(rules_client, "scope", None),
                )
            except Exception:
                pass

    def _compile_rule(self, rule: Any) -> None:
        """Compiles a rule definition into runtime regex and condition patterns."""
        if not getattr(rule, "enabled", True):
            self._compiled_rule_patterns.pop(getattr(rule, "rule_id", ""), None)
            return

        import re
        rule_id = getattr(rule, "rule_id", str(id(rule)))
        conditions = getattr(rule, "conditions", [])
        patterns = []
        for cond in conditions:
            field = getattr(cond, "field", "")
            val = getattr(cond, "value", "")
            op = getattr(cond, "operator", "==")
            if field in ("prompt", "text", "query", "content", "keyword") and isinstance(val, str):
                try:
                    if op in ("contains", "=="):
                        patterns.append(re.compile(re.escape(val), re.IGNORECASE))
                    elif op in ("regex", "matches"):
                        patterns.append(re.compile(val, re.IGNORECASE))
                except Exception:
                    pass

        self._compiled_rule_patterns[rule_id] = {
            "rule": rule,
            "patterns": patterns,
            "action": getattr(rule, "action", "block"),
            "message": getattr(rule, "message", None) or getattr(rule, "name", "Rule violation"),
        }

    def _on_rule_change(self, event: Any) -> None:
        """Push event handler triggered directly when a rule changes in rules layer."""
        event_type = getattr(event, "event_type", "")
        rule = getattr(event, "rule", None)
        if not rule:
            return

        rule_id = getattr(rule, "rule_id", "")
        if event_type in ("CREATED", "UPDATED", "TOGGLED"):
            self._compile_rule(rule)
        elif event_type == "DELETED":
            self._compiled_rule_patterns.pop(rule_id, None)

    def _evaluate_compiled_rules(self, text: str) -> Tuple[bool, Optional[str], List[str]]:
        """Evaluates input text against compiled dynamic rules."""
        matched_patterns = []
        for rule_id, data in list(self._compiled_rule_patterns.items()):
            rule = data["rule"]
            if not getattr(rule, "enabled", True):
                continue
            for pat in data["patterns"]:
                if pat.search(text):
                    matched_patterns.append(pat.pattern)
                    return True, data["message"], matched_patterns

        # Also fallback to direct rules_client evaluate if available
        if self.rules_client and hasattr(self.rules_client, "evaluate"):
            try:
                res = self.rules_client.evaluate({"prompt": text})
                if not getattr(res, "allowed", True):
                    reason = getattr(res, "reason", "Violated rule policy")
                    return True, reason, [reason]
            except Exception:
                pass

        return False, None, []

    def set_severity_threshold(self, threshold: SeverityLevel) -> None:
        """Programmatically update runtime safety threshold (allow, warn, redact, block, strict)."""
        clean = threshold.lower()
        if clean not in SEVERITY_ORDER:
            raise ValueError(f"Invalid severity threshold '{threshold}'. Expected one of {list(SEVERITY_ORDER.keys())}")
        self.severity_threshold = cast(SeverityLevel, clean)

    def evaluate(self, request: Any) -> SafetyCheckResult:
        """
        Evaluates input text sequentially across crisis, injection, and sanitization gates.
        Enforces configurable severity levels and writes non-allow events to the audit log.
        In strict mode, warnings and PII leaks escalate to block.
        """
        if isinstance(request, str):
            request = SafetyCheckRequest(prompt=request)
        text = request.prompt.strip()
        threshold_rank = SEVERITY_ORDER.get(self.severity_threshold, 1)
        is_strict = self.severity_threshold == "strict"

        # Gate 1: Crisis & Self-Harm Circuit-Breaker (Highest Priority)
        is_crisis, crisis_cat, crisis_msg = self.crisis_handler.check_with_category(text)
        if is_crisis:
            threat_cat = f"crisis_{crisis_cat}" if crisis_cat else "crisis_self_harm"
            result = SafetyCheckResult(
                action="crisis_intervention",
                severity="crisis",
                threat_category=cast(ThreatCategory, threat_cat),
                sanitized_prompt=None,
                reason="Self-harm or crisis situation detected. Circuit breaker triggered.",
                crisis_response=crisis_msg,
                matched_patterns=[f"crisis_{crisis_cat or 'self_harm'}_regex"],
            )
            self._log_if_needed(request, result)
            return result

        # Gate 2: Prompt Injection and Adversarial Jailbreak Detection
        is_jailbreak, matches = self.jailbreak_detector.detect(text)
        if is_jailbreak:
            action: SafetyAction = "block" if (is_strict or SEVERITY_ORDER["block"] >= threshold_rank) else "warn"
            result = SafetyCheckResult(
                action=action,
                severity="strict" if is_strict else "block",
                threat_category="prompt_injection" if any("ignore" in m.lower() or "override" in m.lower() for m in matches) else "jailbreak",
                sanitized_prompt=None if action == "block" else text,
                reason=f"Adversarial prompt injection or jailbreak detected: {', '.join(matches[:2])}",
                crisis_response=None,
                matched_patterns=matches,
            )
            self._log_if_needed(request, result)
            return result

        # Gate 2.5: Dynamic Compiled Rules Gate (from Rules Layer)
        rule_blocked, rule_reason, rule_matches = self._evaluate_compiled_rules(text)
        if rule_blocked:
            action_rule: SafetyAction = "block" if (is_strict or SEVERITY_ORDER["block"] >= threshold_rank) else "warn"
            result = SafetyCheckResult(
                action=action_rule,
                severity="strict" if is_strict else "block",
                threat_category="rule_violation",
                sanitized_prompt=None if action_rule == "block" else text,
                reason=f"Blocked by dynamic rule: {rule_reason}",
                crisis_response=None,
                matched_patterns=rule_matches,
            )
            self._log_if_needed(request, result)
            return result

        # Gate 3: PII & Credential Sanitization
        sanitized_text, was_redacted, pii_types = self.pii_detector.sanitize(text)
        if was_redacted:
            action_pii: SafetyAction = "block" if is_strict else ("redact" if SEVERITY_ORDER["redact"] >= threshold_rank else "warn")
            result = SafetyCheckResult(
                action=action_pii,
                severity="strict" if is_strict else "redact",
                threat_category="pii_leak",
                sanitized_prompt=None if action_pii == "block" else sanitized_text,
                reason=f"Sensitive PII detected ({', '.join(pii_types)}) - blocked under strict policy" if is_strict else f"Sensitive PII or credentials detected and redacted: {', '.join(pii_types)}",
                crisis_response=None,
                matched_patterns=pii_types,
            )
            self._log_if_needed(request, result)
            return result

        # Gate 4: Allow clean request
        return SafetyCheckResult(
            action="allow",
            severity="allow",
            threat_category="none",
            sanitized_prompt=text,
            reason="Prompt passed all safety evaluations cleanly.",
            crisis_response=None,
            matched_patterns=[],
        )

    def _log_if_needed(self, request: SafetyCheckRequest, result: SafetyCheckResult) -> None:
        """Appends security event to the audit log for non-allow actions."""
        if result.action != "allow" and self.audit_logger:
            try:
                self.audit_logger.log_event(
                    action=result.action,
                    threat_category=result.threat_category,
                    prompt=request.prompt,
                    actor=request.actor,
                    matched_patterns=result.matched_patterns,
                    reason=result.reason,
                    metadata={"severity": result.severity},
                )
            except Exception:
                pass
