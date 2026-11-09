"""Compensation Manager: Action rollback and undo handlers for reversible mutations.

Feature: 5.24
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
import uuid


@dataclass
class CompensationHook:
    hook_id: str
    action_name: str
    description: str
    rollback_fn: Callable[[], bool]
    session_id: str


class CompensationManager:
    """Tracks and executes compensation routines when actions fail or are cancelled."""

    def __init__(self):
        self._hooks: Dict[str, CompensationHook] = {}

    def register_compensation(
        self,
        action_name: str,
        rollback_fn: Callable[[], bool],
        description: str = "",
        session_id: str = "default",
    ) -> str:
        """Registers a compensating undo handler for an executed mutating action."""
        hook_id = f"cmp_{uuid.uuid4().hex[:8]}"
        hook = CompensationHook(
            hook_id=hook_id,
            action_name=action_name,
            description=description,
            rollback_fn=rollback_fn,
            session_id=session_id,
        )
        self._hooks[hook_id] = hook
        return hook_id

    def rollback(self, hook_id: str) -> bool:
        """Executes the specific compensation hook."""
        hook = self._hooks.pop(hook_id, None)
        if not hook:
            return False
        try:
            return bool(hook.rollback_fn())
        except Exception:
            return False

    def rollback_session(self, session_id: str) -> int:
        """Rolls back all registered actions in a session in reverse order (LIFO)."""
        session_hooks = [h for h in self._hooks.values() if h.session_id == session_id]
        success_count = 0

        # Reverse order for safe unwinding
        for hook in reversed(session_hooks):
            del self._hooks[hook.hook_id]
            try:
                if hook.rollback_fn():
                    success_count += 1
            except Exception:
                pass

        return success_count

    def clear(self) -> None:
        self._hooks.clear()
