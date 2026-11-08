"""Agent Instantiator: Executes compiled agent specifications in an active runtime context."""

import time
from typing import List, Optional
from ..core.interfaces import BaseAgentInstantiator
from ..core.models import (
    AgentExecutionResult,
    AgentSpecification,
)


class AgentInstantiator(BaseAgentInstantiator):
    """Bridges synthesized specifications to runtime execution pipelines."""

    def execute_agent(
        self, spec: AgentSpecification, input_prompt: str
    ) -> AgentExecutionResult:
        start_time = time.perf_counter()

        # Simulate execution leveraging bound persona and tools
        invoked_tools: List[str] = []
        for tool_id in spec.tool_binding.tool_ids[:2]:  # Invoke top relevant tools
            invoked_tools.append(tool_id)

        response_text = (
            f"[{spec.name} - {spec.persona.role}]\n"
            f"Executed directive: '{input_prompt}' using models {spec.model_binding.primary_model}.\n"
            f"Active rules enforced: {', '.join(spec.rules_binding.active_rules)}.\n"
            f"Tools leveraged: {', '.join(invoked_tools)}."
        )

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return AgentExecutionResult(
            agent_id=spec.agent_id,
            prompt=input_prompt,
            response_text=response_text,
            tools_invoked=invoked_tools,
            status="completed",
            duration_ms=round(duration_ms, 2),
        )
