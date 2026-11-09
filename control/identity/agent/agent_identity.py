"""Agent Identity, Scoped Credentials, Attribution & Mutual Auth (Layer 12: IAM, Task 12.4).

Features:
- 12.16: Distinct cryptographic identity for every autonomous agent and sub-agent
- 12.17: Scoped, short-lived agent credentials (e.g., 15-minute task-bound tokens)
- 12.18: Attribution of every executed action to both the agent and delegating parent user
- 12.19: Mutual agent-to-agent authentication for distributed multi-agent handoffs
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("control.identity.agent")


@dataclass
class AgentIdentity:
    """Distinct identity registration for an agent/bot."""
    agent_id: str
    name: str
    parent_user_id: str
    tenant_id: str = "default"
    capabilities: Set[str] = field(default_factory=lambda: {"tool:execute", "memory:read"})
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AgentCredential:
    """Scoped, short-lived credential issued to an agent for task execution."""
    token: str
    agent_id: str
    parent_user_id: str
    tenant_id: str
    capabilities: Set[str]
    task_id: Optional[str]
    issued_at: float
    expires_at: float
    revoked: bool = False

    def is_valid(self) -> bool:
        return (not self.revoked) and (time.time() < self.expires_at)


@dataclass
class ActionAttribution:
    """Audit record attributing an executed action to both the agent and parent user."""
    action_id: str
    action_name: str
    agent_id: str
    parent_user_id: str
    tenant_id: str
    task_id: Optional[str]
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentIdentityManager:
    """Manages autonomous agent identities, short-lived tokens, mutual auth, and action attribution."""

    def __init__(self):
        self._agents: Dict[str, AgentIdentity] = {}
        self._credentials: Dict[str, AgentCredential] = {}  # token -> credential
        self._attributions: List[ActionAttribution] = []
        self._m2m_secret = secrets.token_hex(32)

    def register_agent(
        self,
        agent_id: str,
        name: str,
        parent_user_id: str,
        tenant_id: str = "default",
        capabilities: Optional[Set[str]] = None,
    ) -> AgentIdentity:
        """Registers a new agent identity bound to a parent delegating user."""
        agent = AgentIdentity(
            agent_id=agent_id,
            name=name,
            parent_user_id=parent_user_id,
            tenant_id=tenant_id,
            capabilities=capabilities or {"tool:execute", "memory:read"},
        )
        self._agents[agent_id] = agent
        return agent

    def issue_credential(
        self,
        agent_id: str,
        task_id: Optional[str] = None,
        ttl_seconds: int = 900,  # 15 minutes default
        capabilities: Optional[Set[str]] = None,
    ) -> AgentCredential:
        """Generates a scoped, short-lived token bound to the agent and task."""
        agent = self._agents.get(agent_id)
        if not agent or not agent.is_active:
            raise KeyError(f"Agent '{agent_id}' is not registered or inactive")

        effective_caps = capabilities if capabilities is not None else agent.capabilities
        now = time.time()
        token = f"agt_{secrets.token_urlsafe(32)}"

        cred = AgentCredential(
            token=token,
            agent_id=agent_id,
            parent_user_id=agent.parent_user_id,
            tenant_id=agent.tenant_id,
            capabilities=effective_caps,
            task_id=task_id,
            issued_at=now,
            expires_at=now + ttl_seconds,
        )
        self._credentials[token] = cred
        return cred

    def verify_credential(self, token: str, required_capability: Optional[str] = None) -> AgentCredential:
        cred = self._credentials.get(token)
        if not cred:
            raise PermissionError("Invalid agent credential")

        if cred.revoked:
            raise PermissionError("Agent credential has been revoked")

        if time.time() > cred.expires_at:
            raise PermissionError("Agent credential has expired")

        if required_capability and required_capability not in cred.capabilities and "*" not in cred.capabilities:
            raise PermissionError(f"Agent lacks required capability '{required_capability}'")

        return cred

    def revoke_credential(self, token: str) -> None:
        if token in self._credentials:
            self._credentials[token].revoked = True

    def record_attributed_action(
        self,
        token: str,
        action_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> ActionAttribution:
        """Executes verification and records audit attribution to agent + delegating parent user."""
        cred = self.verify_credential(token)
        action_id = f"act-{secrets.token_hex(6)}"

        attr = ActionAttribution(
            action_id=action_id,
            action_name=action_name,
            agent_id=cred.agent_id,
            parent_user_id=cred.parent_user_id,
            tenant_id=cred.tenant_id,
            task_id=cred.task_id,
            details=details or {},
        )
        self._attributions.append(attr)
        return attr

    def get_action_attributions(
        self,
        agent_id: Optional[str] = None,
        parent_user_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> List[ActionAttribution]:
        res = self._attributions
        if agent_id:
            res = [a for a in res if a.agent_id == agent_id]
        if parent_user_id:
            res = [a for a in res if a.parent_user_id == parent_user_id]
        if task_id:
            res = [a for a in res if a.task_id == task_id]
        return list(res)

    # --- 12.19: Mutual Agent-to-Agent Auth ---
    def generate_m2m_handshake(self, source_agent_id: str, target_agent_id: str) -> str:
        """Generates a cryptographic handshake token for agent-to-agent delegation."""
        payload = f"{source_agent_id}->{target_agent_id}:{int(time.time())}"
        sig = hmac.new(self._m2m_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}|{sig}"

    def verify_m2m_handshake(self, handshake_token: str, expected_target_agent_id: str) -> Tuple[bool, str]:
        try:
            payload, sig = handshake_token.rsplit("|", 1)
            expected_sig = hmac.new(self._m2m_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return False, "Invalid handshake signature"

            route, timestamp_str = payload.split(":")
            source_agent, target_agent = route.split("->")

            if target_agent != expected_target_agent_id:
                return False, f"Handshake target mismatch (expected {expected_target_agent_id}, got {target_agent})"

            if abs(time.time() - float(timestamp_str)) > 300:  # 5 min replay window
                return False, "Handshake token expired or replay attack"

            return True, source_agent
        except Exception as exc:
            return False, f"Handshake verification failed: {exc}"


# Default singleton
default_agent_identity_manager = AgentIdentityManager()

