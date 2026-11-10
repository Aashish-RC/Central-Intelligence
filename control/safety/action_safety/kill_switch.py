"""
Emergency Agent Kill Switch (10.24)
Provides deterministic, sub-second halting of ALL active and pending agent operations
across tenant, user, or individual agent scopes.
Freezes execution state snapshots and immediately aborts in-flight tool actions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class KillSwitchScope(str, Enum):
    GLOBAL = "global"
    TENANT = "tenant"
    USER = "user"
    AGENT = "agent"


class AgentHaltedError(RuntimeError):
    """Raised when an action or agent runner attempts execution while halted by kill switch."""
    def __init__(self, message: str, event: Optional[KillSwitchEvent] = None):
        super().__init__(message)
        self.event = event


@dataclass
class KillSwitchEvent:
    scope: KillSwitchScope
    tenant_id: str = "default"
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    triggered_at: float = field(default_factory=time.time)
    reason: str = "Emergency kill switch triggered"
    actor: str = "system"
    frozen_state: Dict[str, Any] = field(default_factory=dict)
    active: bool = True


class AgentKillSwitch:
    """
    Sub-second Emergency Kill Switch for autonomous agent operations (Feature 10.24).
    Guarantees immediate halt in < 1 second (< 1ms in-memory), state freezing,
    and cancellation of pending tasks.
    """

    def __init__(self):
        self._global_halt: Optional[KillSwitchEvent] = None
        self._tenant_halts: Dict[str, KillSwitchEvent] = {}
        self._user_halts: Dict[str, KillSwitchEvent] = {}
        self._agent_halts: Dict[str, KillSwitchEvent] = {}
        self._registered_cancellables: Dict[str, Tuple[Callable[[], Any], Dict[str, Any]]] = {}

    def trigger(
        self,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        reason: str = "Emergency agent kill switch activated",
        actor: str = "security_admin",
        current_state: Optional[Dict[str, Any]] = None,
        is_global: bool = False,
    ) -> KillSwitchEvent:
        """
        Immediately trips the kill switch for the specified scope.
        Freezes current execution state and triggers immediate cancellation
        of any registered active callbacks.
        """
        frozen = dict(current_state or {})
        frozen["halted_at_timestamp"] = time.time()

        if is_global:
            event = KillSwitchEvent(
                scope=KillSwitchScope.GLOBAL,
                tenant_id="*",
                reason=reason,
                actor=actor,
                frozen_state=frozen,
            )
            self._global_halt = event
        elif agent_id:
            event = KillSwitchEvent(
                scope=KillSwitchScope.AGENT,
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
                reason=reason,
                actor=actor,
                frozen_state=frozen,
            )
            self._agent_halts[f"{tenant_id}:{agent_id}"] = event
        elif user_id:
            event = KillSwitchEvent(
                scope=KillSwitchScope.USER,
                tenant_id=tenant_id,
                user_id=user_id,
                reason=reason,
                actor=actor,
                frozen_state=frozen,
            )
            self._user_halts[f"{tenant_id}:{user_id}"] = event
        else:
            event = KillSwitchEvent(
                scope=KillSwitchScope.TENANT,
                tenant_id=tenant_id,
                reason=reason,
                actor=actor,
                frozen_state=frozen,
            )
            self._tenant_halts[tenant_id] = event

        # Cancel any pending registered tasks in scope
        self._cancel_pending_in_scope(tenant_id=tenant_id, user_id=user_id, agent_id=agent_id, is_global=is_global)
        return event

    def _cancel_pending_in_scope(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        is_global: bool = False,
    ) -> int:
        cancelled_count = 0
        to_remove = []
        for task_id, (cb, scope_meta) in self._registered_cancellables.items():
            match = is_global
            if not match:
                if scope_meta.get("tenant_id") == tenant_id:
                    if user_id and scope_meta.get("user_id") == user_id:
                        match = True
                    elif agent_id and scope_meta.get("agent_id") == agent_id:
                        match = True
                    elif not user_id and not agent_id:
                        match = True

            if match:
                try:
                    cb()
                    cancelled_count += 1
                except Exception:
                    pass
                to_remove.append(task_id)

        for tid in to_remove:
            self._registered_cancellables.pop(tid, None)

        return cancelled_count

    def register_cancellable(
        self,
        task_id: str,
        cancel_callback: Callable[[], Any],
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> None:
        """Registers an in-flight operation callback that will be called if the kill switch trips."""
        self._registered_cancellables[task_id] = (
            cancel_callback,
            {"tenant_id": tenant_id, "user_id": user_id, "agent_id": agent_id},
        )

    def unregister_cancellable(self, task_id: str) -> None:
        self._registered_cancellables.pop(task_id, None)

    def is_halted(
        self,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> bool:
        """Fast sub-millisecond check for whether execution is halted for this target."""
        if self._global_halt and self._global_halt.active:
            return True

        if tenant_id in self._tenant_halts and self._tenant_halts[tenant_id].active:
            return True

        if user_id:
            user_key = f"{tenant_id}:{user_id}"
            if user_key in self._user_halts and self._user_halts[user_key].active:
                return True

        if agent_id:
            agent_key = f"{tenant_id}:{agent_id}"
            if agent_key in self._agent_halts and self._agent_halts[agent_key].active:
                return True

        return False

    def assert_not_halted(
        self,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> None:
        """Raises AgentHaltedError if target scope is currently killed."""
        event = self.get_active_halt_event(tenant_id, user_id, agent_id)
        if event:
            raise AgentHaltedError(
                f"Agent execution halted by Emergency Kill Switch ({event.scope.value} scope): {event.reason}",
                event=event,
            )

    def get_active_halt_event(
        self,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Optional[KillSwitchEvent]:
        if self._global_halt and self._global_halt.active:
            return self._global_halt

        if tenant_id in self._tenant_halts and self._tenant_halts[tenant_id].active:
            return self._tenant_halts[tenant_id]

        if user_id:
            user_key = f"{tenant_id}:{user_id}"
            if user_key in self._user_halts and self._user_halts[user_key].active:
                return self._user_halts[user_key]

        if agent_id:
            agent_key = f"{tenant_id}:{agent_id}"
            if agent_key in self._agent_halts and self._agent_halts[agent_key].active:
                return self._agent_halts[agent_key]

        return None

    def reset(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        is_global: bool = False,
    ) -> None:
        """Resets the kill switch, re-enabling agent operations."""
        if is_global:
            self._global_halt = None
        if agent_id and tenant_id:
            self._agent_halts.pop(f"{tenant_id}:{agent_id}", None)
        elif user_id and tenant_id:
            self._user_halts.pop(f"{tenant_id}:{user_id}", None)
        elif tenant_id:
            self._tenant_halts.pop(tenant_id, None)
        else:
            self._global_halt = None
            self._tenant_halts.clear()
            self._user_halts.clear()
            self._agent_halts.clear()


# Default process-level kill switch singleton
default_kill_switch = AgentKillSwitch()
