"""Tenant-Level Sandbox and Simulation Test Mode (Layer 11: Evaluation & Quality, Feature 11.25).

Provides tenant-scoped simulation mode where mutating actions (emails, payments, external API calls)
are intercepted, safely simulated, and flagged without executing real side-effects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("control.evaluation.sandbox")

MUTATING_ACTION_KEYWORDS = {
    "send", "email", "pay", "charge", "delete", "remove", "drop",
    "modify", "update", "publish", "deploy", "post", "transfer", "write"
}


@dataclass
class SimulatedActionRecord:
    """Audit record of a simulated mutating action."""
    action_id: str
    tenant_id: str
    tool_name: str
    parameters: Dict[str, Any]
    simulated_output: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TenantSandboxConfig:
    """Sandbox policy configuration per tenant."""
    tenant_id: str
    enabled: bool = True
    whitelist_live_tools: Set[str] = field(default_factory=lambda: {"read_file", "get", "query", "search"})
    mock_responses: Dict[str, Any] = field(default_factory=dict)


class TenantSandboxManager:
    """Manages tenant-level sandbox states, intercepting mutating tool actions during test/dry-run mode."""

    def __init__(self):
        self._tenant_configs: Dict[str, TenantSandboxConfig] = {}
        self._audit_log: List[SimulatedActionRecord] = []

    def enable_sandbox(
        self,
        tenant_id: str,
        whitelist_live_tools: Optional[Set[str]] = None,
        mock_responses: Optional[Dict[str, Any]] = None,
    ) -> TenantSandboxConfig:
        config = TenantSandboxConfig(
            tenant_id=tenant_id,
            enabled=True,
            whitelist_live_tools=whitelist_live_tools or {"read_file", "get", "query", "search"},
            mock_responses=mock_responses or {},
        )
        self._tenant_configs[tenant_id] = config
        return config

    def disable_sandbox(self, tenant_id: str) -> None:
        if tenant_id in self._tenant_configs:
            self._tenant_configs[tenant_id].enabled = False

    def is_sandbox_active(self, tenant_id: str) -> bool:
        config = self._tenant_configs.get(tenant_id)
        return config.enabled if config else False

    def should_simulate(self, tool_name: str, tenant_id: str) -> bool:
        if not self.is_sandbox_active(tenant_id):
            return False

        config = self._tenant_configs[tenant_id]
        if tool_name.lower() in {t.lower() for t in config.whitelist_live_tools}:
            return False

        # If tool name matches mutating keywords or not whitelisted in sandbox
        tool_lower = tool_name.lower()
        is_mutating = any(kw in tool_lower for kw in MUTATING_ACTION_KEYWORDS)
        return is_mutating or (tool_lower not in config.whitelist_live_tools)

    def intercept(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        tenant_id: str = "default",
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Intercepts tool execution if sandbox active.

        Returns:
            (is_simulated: bool, simulated_output: Optional[Dict[str, Any]])
        """
        if not self.should_simulate(tool_name, tenant_id):
            return False, None

        config = self._tenant_configs[tenant_id]
        custom_mock = config.mock_responses.get(tool_name)

        action_id = f"sim-act-{len(self._audit_log)+1:04d}"
        simulated_output = custom_mock or {
            "status": "simulated_success",
            "is_simulation": True,
            "tenant_id": tenant_id,
            "tool": tool_name,
            "parameters": parameters,
            "message": f"[SANDBOX MODE] Simulated execution of '{tool_name}' without external side-effects.",
        }

        record = SimulatedActionRecord(
            action_id=action_id,
            tenant_id=tenant_id,
            tool_name=tool_name,
            parameters=parameters,
            simulated_output=simulated_output,
        )
        self._audit_log.append(record)

        return True, simulated_output

    def get_simulated_actions(self, tenant_id: Optional[str] = None) -> List[SimulatedActionRecord]:
        if tenant_id:
            return [a for a in self._audit_log if a.tenant_id == tenant_id]
        return list(self._audit_log)


# Global singleton
default_tenant_sandbox = TenantSandboxManager()

