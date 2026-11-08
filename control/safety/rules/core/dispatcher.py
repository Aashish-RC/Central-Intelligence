"""
Pheonix Rules Event Dispatcher
Real-time subscriber notification bus for instantaneous rule propagation across components.
"""

from typing import Callable, Dict, Optional, Any
from ..models import RuleChangeEvent, RuleScope


class RuleDispatcher:
    """Manages connected application subscriptions and broadcasts rule lifecycle events."""

    def __init__(self):
        # subscriber_id -> (callback, scope_filter)
        self._subscribers: Dict[str, tuple[Callable[[RuleChangeEvent], None], Optional[RuleScope]]] = {}

    def subscribe(
        self,
        subscriber_id: str,
        callback: Callable[[RuleChangeEvent], None],
        scope_filter: Optional[RuleScope] = None,
    ):
        """Register an application callback listener for rule changes."""
        self._subscribers[subscriber_id] = (callback, scope_filter)

    def unsubscribe(self, subscriber_id: str):
        """Deregister an application callback."""
        self._subscribers.pop(subscriber_id, None)

    def broadcast(self, event: RuleChangeEvent):
        """
        Broadcast rule change event to all matching registered subscribers.
        Done when: A rule change reaches every app.
        """
        rule_scope = event.rule.scope

        for sub_id, (cb, filter_scope) in list(self._subscribers.items()):
            # Notify if subscriber listens to all scopes, or rule is GLOBAL, or scopes match
            if (
                filter_scope is None
                or filter_scope == RuleScope.GLOBAL
                or rule_scope == RuleScope.GLOBAL
                or filter_scope == rule_scope
            ):
                try:
                    cb(event)
                except Exception as e:
                    # Log or ignore callback errors so other subscribers still receive updates
                    pass

    def subscriber_count(self) -> int:
        return len(self._subscribers)
