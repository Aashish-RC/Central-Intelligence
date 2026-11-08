"""Unit tests for BudgetGuard cost constraints and spending limits."""

import pytest
from orchestrator.core.models import TaskStatus
from orchestrator.engine.dag_runner import ParallelDAGRunner
from orchestrator.guard.budget_guard import BudgetGuard
from orchestrator.planner.multi_step_planner import MultiStepPlanner


def test_budget_rejection_when_estimate_exceeds_limit():
    guard = BudgetGuard()
    planner = MultiStepPlanner()
    runner = ParallelDAGRunner(budget_guard=guard)

    specs = [
        {"id": "heavy1", "cost_estimate": 0.8, "depends_on": []},
        {"id": "heavy2", "cost_estimate": 0.5, "depends_on": []},
    ]
    # Total cost = 1.3, but budget_limit is 1.0
    plan = planner.create_plan("Overbudget Plan", specs, budget_limit=1.0)
    assert not guard.validate_plan_budget(plan)

    report = runner.run_plan(plan)
    assert report.status == TaskStatus.FAILED
    assert "Budget exceeded" in report.node_results["heavy1"].error


def test_spend_tracking_on_completion():
    guard = BudgetGuard()
    planner = MultiStepPlanner()
    runner = ParallelDAGRunner(budget_guard=guard)

    specs = [
        {"id": "step1", "cost_estimate": 0.05, "depends_on": []},
        {"id": "step2", "cost_estimate": 0.15, "depends_on": ["step1"]},
    ]
    plan = planner.create_plan("Affordable Plan", specs, budget_limit=1.0)
    assert guard.validate_plan_budget(plan)

    report = runner.run_plan(plan)
    assert report.status == TaskStatus.COMPLETED
    assert round(report.total_cost, 2) == 0.20
