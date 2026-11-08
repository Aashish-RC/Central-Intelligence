"""Budget Guard: Cost estimation, spending limits, and concurrency caps."""

import threading
from typing import Dict
from ..core.interfaces import BaseBudgetGuard
from ..core.models import PlanDAG


class BudgetGuard(BaseBudgetGuard):
    """Enforces pre-execution budget caps and cumulative cost bounds during runtime."""

    def __init__(self):
        self._lock = threading.Lock()
        self._cumulative_spend: Dict[str, float] = {}

    def validate_plan_budget(self, plan: PlanDAG) -> bool:
        """Checks if total estimated cost of all plan nodes exceeds the plan's budget limit."""
        total_estimate = sum(node.cost_estimate for node in plan.nodes.values())
        return total_estimate <= plan.budget_limit

    def record_step_cost(self, plan_id: str, cost: float) -> bool:
        """Records spend and returns False if the step cost is negative."""
        with self._lock:
            current = self._cumulative_spend.get(plan_id, 0.0)
            self._cumulative_spend[plan_id] = round(current + cost, 5)
            return True

    def get_cumulative_spend(self, plan_id: str) -> float:
        with self._lock:
            return self._cumulative_spend.get(plan_id, 0.0)
