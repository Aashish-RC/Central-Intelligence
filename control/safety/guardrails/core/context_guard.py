"""
Pheonix Multi-Turn Context Guardrail
Accumulates multi-turn conversation trajectories and evaluates the holistic running context
against adversarial attacks, semantic fragmentation, and incremental jailbreaks.
"""

import re
from typing import Dict, List, Optional, Any
from ..models import SafetyCheckRequest, SafetyCheckResult
from .engine import GuardrailsEngine


class MultiTurnContextGuard:
    """
    Maintains running conversation history per session and evaluates both
    incremental turns and the accumulated trajectory.
    """

    def __init__(self, engine: Optional[GuardrailsEngine] = None, max_history_turns: int = 10):
        self.engine = engine or GuardrailsEngine()
        self.max_history_turns = max_history_turns
        # session_id -> list of {"role": str, "content": str}
        self._conversations: Dict[str, List[Dict[str, Any]]] = {}

    def clear(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        if session_id in self._conversations:
            del self._conversations[session_id]

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve stored turns for a session."""
        return self._conversations.get(session_id, [])

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        """Record a turn in the session dialogue history."""
        if session_id not in self._conversations:
            self._conversations[session_id] = []
        self._conversations[session_id].append({"role": role, "content": content})
        if len(self._conversations[session_id]) > self.max_history_turns * 2:
            self._conversations[session_id] = self._conversations[session_id][-self.max_history_turns * 2:]

    def evaluate_turn(
        self,
        session_id: str,
        new_prompt: str,
        role: str = "user",
    ) -> SafetyCheckResult:
        """
        Evaluate a new message in the context of previous conversation turns.
        1. Evaluates new_prompt individually.
        2. If clean individually, evaluates the synthesized multi-turn context window.
        3. Detects fragmented across-turn adversarial intent.
        4. If allowed, appends new_prompt to session history.
        """
        # 1. Evaluate single turn individually
        single_req = SafetyCheckRequest(prompt=new_prompt, session_id=session_id)
        single_res = self.engine.evaluate(single_req)
        if single_res.action != "allow":
            return single_res

        # 2. Re-evaluate running context window
        history = self._conversations.get(session_id, [])
        if history:
            context_pieces = [turn["content"] for turn in history if turn["role"] == "user"]
            context_pieces.append(new_prompt)
            accumulated_text = " \n ".join(context_pieces)

            # Direct evaluation of accumulated dialogue
            accumulated_req = SafetyCheckRequest(prompt=accumulated_text, session_id=session_id)
            accumulated_res = self.engine.evaluate(accumulated_req)

            if accumulated_res.action != "allow":
                return SafetyCheckResult(
                    action=accumulated_res.action,
                    threat_category=accumulated_res.threat_category,
                    sanitized_prompt=None,
                    reason=f"Multi-turn adversarial correlation detected: {accumulated_res.reason}",
                    crisis_response=accumulated_res.crisis_response,
                    matched_patterns=accumulated_res.matched_patterns,
                )

            # 3. Detect fragmented intent split across turns
            lower_history = [t.lower() for t in context_pieces]
            has_action = any(re.search(r"\b(?:ignore|disregard|forget|bypass|override)\b", t) for t in lower_history)
            has_qualifier = any(re.search(r"\b(?:all|previous|prior|above|system|core)\b", t) for t in lower_history)
            has_target = any(re.search(r"\b(?:instructions|rules|directives|prompts|guidelines|dan)\b", t) for t in lower_history)

            if has_action and has_qualifier and has_target:
                return SafetyCheckResult(
                    action="block",
                    threat_category="jailbreak",
                    sanitized_prompt=None,
                    reason="Multi-turn adversarial correlation detected: fragmented prompt injection across turns",
                    crisis_response=None,
                    matched_patterns=["multi_turn_fragmented_jailbreak"]
                )

        # 4. Clean turn: commit to history
        self.add_turn(session_id, role, new_prompt)
        return single_res
