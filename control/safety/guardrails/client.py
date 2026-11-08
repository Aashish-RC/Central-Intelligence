"""
Pheonix Guardrails Client SDK
High-level client for applications, memory engine, and agents to evaluate and sanitize prompts.
"""

from typing import Any, Optional
from .models import SafetyCheckRequest, SafetyCheckResult
from .core.engine import GuardrailsEngine
from .core.output_guard import OutputGuard, OutputCheckResult
from .core.tool_output_guard import ToolOutputGuard, ToolOutputScanResult
from .core.context_guard import MultiTurnContextGuard


class GuardrailsClient:
    """
    Unified client for interacting with Pheonix Guardrails and Safety:
    inbound prompts, outbound generation, tool outputs, and multi-turn context.
    """

    def __init__(self, engine: Optional[GuardrailsEngine] = None):
        self.engine = engine or GuardrailsEngine()
        self._output_guard = OutputGuard()
        self._tool_output_guard = ToolOutputGuard()
        self._context_guard = MultiTurnContextGuard(engine=self.engine)

    def check(self, prompt: str, actor: str = "anonymous") -> SafetyCheckResult:
        """Runs prompt through full guardrails pipeline."""
        req = SafetyCheckRequest(prompt=prompt, actor=actor)
        return self.engine.evaluate(req)

    def check_output(self, generated_text: str) -> OutputCheckResult:
        """Scans model-generated output for prohibited material or secret leaks."""
        return self._output_guard.evaluate(generated_text)

    def check_tool_output(self, tool_output: Any, tool_name: str = "tool") -> ToolOutputScanResult:
        """Scans tool return values for indirect prompt injection before feeding into model context."""
        return self._tool_output_guard.scan(tool_output, tool_name=tool_name)

    def check_turn(self, session_id: str, prompt: str, role: str = "user") -> SafetyCheckResult:
        """Evaluates prompt within the accumulated multi-turn conversation context."""
        return self._context_guard.evaluate_turn(session_id, prompt, role=role)

    def is_safe(self, prompt: str) -> bool:
        """Returns True if prompt is permitted (allowed or cleanly redacted)."""
        result = self.check(prompt)
        return result.action in ["allow", "redact"]

    def sanitize_prompt(self, prompt: str) -> str:
        """
        Returns sanitized prompt if allowed or redacted.
        Raises ValueError if prompt is blocked or triggers crisis intervention.
        """
        result = self.check(prompt)
        if result.action == "block":
            raise ValueError(f"Prompt blocked by guardrails: {result.reason}")
        if result.action == "crisis_intervention":
            raise ValueError(f"Crisis intervention triggered: {result.crisis_response}")
        return result.sanitized_prompt or prompt

