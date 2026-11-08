"""
Tests for persistent background scheduling surviving process reboots.
"""

from internal_agents.core.models import AgentType, AgentRunReport
from internal_agents.scheduler.background_runner import BackgroundAgentScheduler
from internal_agents.storage.sqlite_agent_log import SQLiteAgentLogStore
from internal_agents.core.interfaces import BaseInternalAgent


class DummyAgent(BaseInternalAgent):
    def __init__(self, _agent_type: AgentType, store):
        self._type = _agent_type
        self.store = store

    @property
    def agent_type(self) -> AgentType:
        return self._type

    def run_cycle(self) -> AgentRunReport:
        return AgentRunReport(
            agent_type=self.agent_type,
            success=True,
            items_processed=5,
            findings=[],
        )


def test_persistent_scheduler_lifecycle(tmp_path):
    db_file = str(tmp_path / "scheduler.db")
    store = SQLiteAgentLogStore(db_path=db_file)
    scheduler = BackgroundAgentScheduler(visible_store=store)

    agent = DummyAgent(AgentType.RESOURCE_MONITOR, store)
    scheduler.register_agent(agent, interval_seconds=45.0)

    # Trigger cycle
    report = scheduler.trigger_cycle(AgentType.RESOURCE_MONITOR)
    assert report.success is True

    schedules = scheduler.get_persistent_schedules()
    assert len(schedules) == 1
    assert schedules[0]["agent_type"] == "resource_monitor"
    assert schedules[0]["interval_seconds"] == 45.0
    assert schedules[0]["total_runs"] == 1
    assert schedules[0]["last_status"] == "success"

    # Simulate reboot: re-instantiate store and scheduler pointing to same DB
    store2 = SQLiteAgentLogStore(db_path=db_file)
    schedules2 = store2.get_schedules()
    assert len(schedules2) == 1
    assert schedules2[0]["agent_type"] == "resource_monitor"
    assert schedules2[0]["total_runs"] == 1
    assert schedules2[0]["interval_seconds"] == 45.0
