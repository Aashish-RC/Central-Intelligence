"""Integration tests for Orchestrator wiring:
- W6: orchestrator -> sandboxes (code execution step)
- W7: orchestrator -> tools_mcp (tool dispatch step)
- W12: orchestrator resource concurrency cap
- W13: orchestrator -> notifications
"""

import pytest
from orchestrator.core.models import TaskStatus
from orchestrator.engine.dag_runner import ParallelDAGRunner
from orchestrator.planner.multi_step_planner import MultiStepPlanner
from sandboxes.manager import SandboxManager
from tools_mcp.runner.dispatcher import ToolDispatcher
from notifications.listener.orchestrator_listener import OrchestratorListener
from notifications.channels.dispatcher import ChannelDispatcher
from notifications.storage.inbox_store import InboxStore


def test_w6_orchestrator_runs_code_in_sandbox(monkeypatch):
    """W6: Orchestrator executes a code node through the sandboxes engine."""
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")
    planner = MultiStepPlanner()
    runner = ParallelDAGRunner(sandbox_manager=SandboxManager())

    specs = [
        {
            "id": "step_compute",
            "title": "Compute factorial in isolated sandbox",
            "action": "code",
            "params": {
                "language": "python",
                "code": "import math\nprint(f'RES:{math.factorial(6)}')",
            },
            "depends_on": [],
        }
    ]

    plan = planner.create_plan("Sandbox Execution Plan", specs)
    report = runner.run_plan(plan)

    assert report.status == TaskStatus.COMPLETED
    assert report.completed_nodes == 1
    assert "RES:720" in report.node_results["step_compute"].output


def test_w7_orchestrator_dispatches_mcp_tool():
    """W7: Orchestrator executes a tool step via tools_mcp catalog & dispatcher."""
    planner = MultiStepPlanner()
    runner = ParallelDAGRunner(tool_dispatcher=ToolDispatcher())

    specs = [
        {
            "id": "step_calc",
            "title": "Evaluate expression via builtin tool",
            "action": "tool:calculator",
            "params": {
                "expression": "sqrt(144) * 5",
            },
            "depends_on": [],
        }
    ]

    plan = planner.create_plan("Tool Call Plan", specs)
    report = runner.run_plan(plan)

    assert report.status == TaskStatus.COMPLETED
    assert report.completed_nodes == 1
    # sqrt(144) * 5 = 12.0 * 5 = 60.0
    assert report.node_results["step_calc"].output == "60.0"


def test_w12_orchestrator_resource_concurrency_throttle():
    """W12: Orchestrator respects max_resource_concurrency throttle cap."""
    planner = MultiStepPlanner()
    runner = ParallelDAGRunner(max_resource_concurrency=2)

    specs = [
        {"id": f"step_{i}", "action": "noop", "depends_on": []}
        for i in range(8)
    ]

    plan = planner.create_plan("Throttled Plan", specs, max_concurrency=10)
    report = runner.run_plan(plan)

    assert report.status == TaskStatus.COMPLETED
    assert report.completed_nodes == 8


def test_w13_orchestrator_fires_notification_event():
    """W13: Completed orchestrator task sends notification via notifications listener."""
    inbox = InboxStore()
    dispatcher = ChannelDispatcher(inbox_store=inbox)
    listener = OrchestratorListener(dispatcher=dispatcher)

    planner = MultiStepPlanner()
    runner = ParallelDAGRunner(notification_listener=listener)

    specs = [
        {"id": "step_1", "action": "noop", "depends_on": []}
    ]

    plan = planner.create_plan("Notify Plan", specs)
    report = runner.run_plan(plan)

    assert report.status == TaskStatus.COMPLETED
    items = inbox.list_notifications()
    assert len(items) > 0
    assert any("Notify Plan" in item.title for item in items)
