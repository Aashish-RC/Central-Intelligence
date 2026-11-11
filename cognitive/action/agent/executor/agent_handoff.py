"""Agent-to-Agent Handoff Protocol (L5 Feature 5.43).

Transfers task ownership cleanly between specialized agents alongside a full
context package (summary, artifacts, constraints, provenance) and returns results.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import uuid4


@dataclass
class HandoffContextPackage:
    """Full structured context passed during agent-to-agent delegation."""

    source_agent: str
    target_agent: str
    task: str
    conversation_summary: str = ""
    findings: List[str] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    handoff_id: str = field(default_factory=lambda: f"hoff_{uuid4().hex[:8]}")
    trace: List[str] = field(default_factory=list)


@dataclass
class HandoffResult:
    """Structured response returned by the receiving agent."""

    handoff_id: str
    source_agent: str
    target_agent: str
    success: bool
    output: Any
    received_context: HandoffContextPackage
    provenance: List[str] = field(default_factory=list)


AgentHandler = Callable[[HandoffContextPackage], Any | Awaitable[Any]]


class AgentHandoffCoordinator:
    """Registry and router for contextual agent-to-agent task handoffs."""

    def __init__(self) -> None:
        self._agents: Dict[str, AgentHandler] = {}
        self._history: List[HandoffResult] = []

    def register_agent(self, agent_id: str, handler: AgentHandler) -> None:
        self._agents[agent_id] = handler

    async def handoff(self, package: HandoffContextPackage) -> HandoffResult:
        """Transfer execution + context package to target agent and return its result."""
        if package.target_agent not in self._agents:
            raise KeyError(f"Target agent '{package.target_agent}' is not registered")

        package.trace.append(f"{package.source_agent}->{package.target_agent}")
        handler = self._agents[package.target_agent]
        out = handler(package)
        if asyncio.iscoroutine(out):
            out = await out

        result = HandoffResult(
            handoff_id=package.handoff_id,
            source_agent=package.source_agent,
            target_agent=package.target_agent,
            success=True,
            output=out,
            received_context=package,
            provenance=list(package.trace),
        )
        self._history.append(result)
        return result

    def get_history(self) -> List[HandoffResult]:
        return list(self._history)

