"""Parlant Behavioral Governor Adapter."""

from typing import Any, Dict, List, Optional
import httpx
from agent.core.manifest import GuardrailConfig
from agent.core.exceptions import GuardrailViolationError


class ParlantAdapter:
    """Adapter for connecting to Parlant behavioral evaluation engine or remote API."""

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url

    async def evaluate_guidelines(
        self,
        prompt: str,
        response: str,
        config: GuardrailConfig,
    ) -> Dict[str, Any]:
        """Evaluate response against Parlant guidelines."""
        # If remote API is configured, call Parlant API
        if self.api_url:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(
                        f"{self.api_url}/v1/guidelines/evaluate",
                        json={
                            "ruleset_id": config.ruleset_id,
                            "prompt": prompt,
                            "response": response,
                            "guidelines": config.guidelines,
                        }
                    )
                    if res.status_code == 200:
                        return res.json()
            except Exception:
                pass

        # Fallback built-in compliance evaluator
        violations: List[str] = []
        lower_resp = response.lower()

        # Check blocked keywords
        for kw in config.blocked_keywords:
            if kw.lower() in lower_resp:
                violations.append(f"Blocked keyword detected: '{kw}'")

        is_compliant = len(violations) == 0
        return {
            "compliant": is_compliant,
            "violations": violations,
            "ruleset_id": config.ruleset_id,
            "engine": "parlant-local-governor",
        }
