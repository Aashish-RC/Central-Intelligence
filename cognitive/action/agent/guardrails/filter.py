"""Guardrails Filter: Intercepts Agent Prompts and Responses against Policies."""

import re
from typing import Any, Dict, List, Optional
from agent.core.manifest import GuardrailConfig
from agent.core.exceptions import GuardrailViolationError
from .parlant_adapter import ParlantAdapter


class GuardrailFilter:
    """Interception filter for prompt sanitization, sensitive data masking, and output validation."""

    # Common credential patterns (API keys, bearer tokens)
    CREDENTIAL_PATTERNS = [
        re.compile(r"(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?([A-Za-z0-9_-]{16,})['\"]?", re.IGNORECASE),
        re.compile(r"Bearer\s+([A-Za-z0-9_\-\.]{20,})", re.IGNORECASE),
    ]

    def __init__(
        self,
        parlant_adapter: Optional[ParlantAdapter] = None,
        rules_client: Optional[Any] = None,
    ):
        self.adapter = parlant_adapter or ParlantAdapter()
        self.rules_client = rules_client
        self._compiled_rule_regexes: List[re.Pattern] = []
        if self.rules_client:
            self._sync_rules()
            if hasattr(self.rules_client, "engine") and hasattr(self.rules_client.engine, "subscribe"):
                try:
                    self.rules_client.engine.subscribe(
                        subscriber_id=f"agent_guardrail_filter_{id(self)}",
                        callback=self._on_rule_change,
                    )
                except Exception:
                    pass

    def _sync_rules(self) -> None:
        if not self.rules_client:
            return
        self._compiled_rule_regexes = []
        rules = getattr(self.rules_client, "_local_rules", {}).values()
        for r in rules:
            if getattr(r, "enabled", True):
                for cond in getattr(r, "conditions", []):
                    val = getattr(cond, "value", None)
                    if val and isinstance(val, str):
                        try:
                            self._compiled_rule_regexes.append(re.compile(re.escape(val), re.IGNORECASE))
                        except Exception:
                            pass

    def _on_rule_change(self, event: Any) -> None:
        self._sync_rules()

    def sanitize_input(self, text: str, config: GuardrailConfig) -> str:
        """Inspect and clean incoming user prompts."""
        # 1. Check against compiled dynamic rules from rules.client
        for pat in self._compiled_rule_regexes:
            if pat.search(text):
                raise GuardrailViolationError(
                    f"Prompt rejected due to dynamic rule violation: '{pat.pattern}'",
                    details={"matched_pattern": pat.pattern}
                )

        if self.rules_client and hasattr(self.rules_client, "evaluate"):
            try:
                res = self.rules_client.evaluate({"prompt": text})
                if not getattr(res, "allowed", True):
                    raise GuardrailViolationError(
                        f"Prompt rejected by rules client: {getattr(res, 'reason', 'Rule violation')}",
                        details={"rule_id": getattr(getattr(res, "matched_rule", None), "rule_id", None)}
                    )
            except GuardrailViolationError:
                raise
            except Exception:
                pass

        # 2. Check manifest blocked keywords
        for kw in config.blocked_keywords:
            if kw.lower() in text.lower():
                raise GuardrailViolationError(
                    f"Prompt rejected due to prohibited term: '{kw}'",
                    details={"blocked_keyword": kw}
                )
        return text

    async def validate_and_filter_output(
        self,
        prompt: str,
        response_text: str,
        config: GuardrailConfig,
    ) -> str:
        """Validate agent output against Parlant guidelines and mask any sensitive leaked tokens."""
        # 1. Mask sensitive credentials if found
        sanitized = response_text
        for pattern in self.CREDENTIAL_PATTERNS:
            sanitized = pattern.sub("[REDACTED_CREDENTIAL]", sanitized)

        # 2. Evaluate against Parlant guidelines and blocked terms
        evaluation = await self.adapter.evaluate_guidelines(
            prompt=prompt,
            response=sanitized,
            config=config,
        )

        if not evaluation.get("compliant", True):
            violations = evaluation.get("violations", ["Compliance policy violation"])
            raise GuardrailViolationError(
                f"Agent response failed behavioral compliance: {', '.join(violations)}",
                details={"violations": violations, "ruleset_id": config.ruleset_id}
            )

        return sanitized
