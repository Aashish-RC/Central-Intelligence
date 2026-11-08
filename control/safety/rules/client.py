"""
Pheonix Rules Client SDK
Enables applications to adopt the rules layer, subscribe to live updates, and evaluate policies locally.
"""

import time
from typing import Dict, Any, Optional, List
from .models import (
    RuleDefinition,
    RuleScope,
    RuleEvaluationResult,
    RuleChangeEvent,
)
from .core.schema import evaluate_rules
from .core.engine import RulesEngine


class RulesClient:
    """
    Client embedded inside applications (e.g., Agent, Model Gateway, Memory).
    Caches active rules in memory and receives live push updates whenever rules change.
    Guarantees: A rule change reaches every app.
    """

    def __init__(
        self,
        app_name: str,
        engine: RulesEngine,
        scope: RuleScope = RuleScope.GLOBAL,
    ):
        self.app_name = app_name
        self.engine = engine
        self.scope = scope
        self._local_rules: Dict[str, RuleDefinition] = {}
        self.last_sync_at: float = 0.0

        # Initial synchronization
        self._sync_all()

        # Subscribe to real-time updates
        self.engine.subscribe(
            subscriber_id=f"client_{app_name}_{id(self)}",
            callback=self._on_rule_change,
            scope_filter=self.scope,
        )

    def _sync_all(self):
        """Fetch all initial rules relevant to this client's scope."""
        rules = self.engine.list_rules(scope=self.scope, enabled_only=False)
        self._local_rules = {r.rule_id: r for r in rules}
        self.last_sync_at = time.time()

    def _on_rule_change(self, event: RuleChangeEvent):
        """
        Push event handler triggered directly by RulesEngine when any rule changes.
        Keeps the local application cache in immediate synchronization.
        """
        rule = event.rule
        if event.event_type in ("CREATED", "UPDATED", "TOGGLED"):
            self._local_rules[rule.rule_id] = rule
        elif event.event_type == "DELETED":
            self._local_rules.pop(rule.rule_id, None)

        self.last_sync_at = time.time()

    def evaluate(self, context: Dict[str, Any]) -> RuleEvaluationResult:
        """
        Evaluate context against locally cached rules with zero network round-trip overhead.
        """
        active_rules = [r for r in self._local_rules.values() if r.enabled]
        return evaluate_rules(active_rules, self.scope, context)

    def get_active_rule_count(self) -> int:
        """Return number of currently active rules in client cache."""
        return len([r for r in self._local_rules.values() if r.enabled])

    def close(self):
        """Deregister client subscription."""
        self.engine.unsubscribe(f"client_{self.app_name}_{id(self)}")
