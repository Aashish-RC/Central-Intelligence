"""Operator Console: Inspection, Pause & Override Controls (Layer 12: IAM, Feature 12.46).

Provides administrative supervisory controls to inspect, pause, override, or terminate
autonomous agent and user activities across the platform.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("control.identity.operator")


class InterventionState(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    OVERRIDDEN = "overridden"
    TERMINATED = "terminated"


@dataclass
class OperatorOverrideRecord:
    """Record of an administrative override or intervention."""
    intervention_id: str
    target_id: str  # user_id or agent_id
    target_type: str  # 'user' or 'agent'
    state: InterventionState
    admin_id: str
    reason: str
    override_payload: Optional[Dict[str, Any]] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OperatorConsole:
    """Administrative console for supervising and pausing agent operations."""

    def __init__(self):
        self._paused_users: Set[str] = set()
        self._paused_agents: Set[str] = set()
        self._overrides: List[OperatorOverrideRecord] = []

    def pause_user_agents(self, user_id: str, admin_id: str, reason: str = "Administrative hold") -> OperatorOverrideRecord:
        """Emergency administrative pause of all agent actions for a user (12.46)."""
        self._paused_users.add(user_id)
        rec = OperatorOverrideRecord(
            intervention_id=f"op-int-{len(self._overrides)+1:04d}",
            target_id=user_id,
            target_type="user",
            state=InterventionState.PAUSED,
            admin_id=admin_id,
            reason=reason,
        )
        self._overrides.append(rec)
        logger.warning(f"Operator {admin_id} paused all agents for user {user_id}: {reason}")
        return rec

    def resume_user_agents(self, user_id: str, admin_id: str) -> None:
        self._paused_users.discard(user_id)
        rec = OperatorOverrideRecord(
            intervention_id=f"op-int-{len(self._overrides)+1:04d}",
            target_id=user_id,
            target_type="user",
            state=InterventionState.ACTIVE,
            admin_id=admin_id,
            reason="Resumed by operator",
        )
        self._overrides.append(rec)

    def pause_agent(self, agent_id: str, admin_id: str, reason: str) -> OperatorOverrideRecord:
        self._paused_agents.add(agent_id)
        rec = OperatorOverrideRecord(
            intervention_id=f"op-int-{len(self._overrides)+1:04d}",
            target_id=agent_id,
            target_type="agent",
            state=InterventionState.PAUSED,
            admin_id=admin_id,
            reason=reason,
        )
        self._overrides.append(rec)
        return rec

    def resume_agent(self, agent_id: str, admin_id: str) -> None:
        self._paused_agents.discard(agent_id)

    def is_execution_allowed(self, user_id: Optional[str] = None, agent_id: Optional[str] = None) -> bool:
        """Checks whether agent execution is permitted or administratively blocked."""
        if user_id and user_id in self._paused_users:
            return False
        if agent_id and agent_id in self._paused_agents:
            return False
        return True

    def override_agent_decision(
        self,
        agent_id: str,
        admin_id: str,
        reason: str,
        forced_decision: Dict[str, Any],
    ) -> OperatorOverrideRecord:
        """Injects administrative override payload replacing model decision."""
        rec = OperatorOverrideRecord(
            intervention_id=f"op-int-{len(self._overrides)+1:04d}",
            target_id=agent_id,
            target_type="agent",
            state=InterventionState.OVERRIDDEN,
            admin_id=admin_id,
            reason=reason,
            override_payload=forced_decision,
        )
        self._overrides.append(rec)
        return rec

    def get_interventions(self, target_id: Optional[str] = None) -> List[OperatorOverrideRecord]:
        if target_id:
            return [o for o in self._overrides if o.target_id == target_id]
        return list(self._overrides)

