"""Tests for SQLiteAgentLogStore and BackgroundAgentScheduler."""

import time
import pytest
from internal_agents.core.models import (
    AgentLogEntry,
    AgentSeverity,
    AgentType,
)
from internal_agents.storage.sqlite_agent_log import SQLiteAgentLogStore
from internal_agents.agents.provider_health import ProviderHealthAgent
from internal_agents.agents.guardrail_review import GuardrailReviewAgent
from internal_agents.agents.resource_monitor import ResourceMonitorAgent
from internal_agents.scheduler.background_runner import BackgroundAgentScheduler


def test_sqlite_agent_log_store_persistence(tmp_path):
    db_file = str(tmp_path / "test_agents.db")
    store = SQLiteAgentLogStore(db_file)

    entry = AgentLogEntry(
        agent_type=AgentType.PROVIDER_HEALTH,
        severity=AgentSeverity.INFO,
        action="ping",
        message="Gemini ping OK (85ms)",
        metadata={"provider": "gemini", "latency": 85},
    )
    store.append_log(entry)

    # Re-open database from file
    store_reopened = SQLiteAgentLogStore(db_file)
    logs = store_reopened.query_logs()
    assert len(logs) == 1
    assert logs[0].id == entry.id
    assert logs[0].message == entry.message
    assert logs[0].metadata["provider"] == "gemini"


def test_background_scheduler_manual_triggers():
    store = SQLiteAgentLogStore(":memory:")
    scheduler = BackgroundAgentScheduler(visible_store=store)

    health_agent = ProviderHealthAgent(
        visible_store=store,
        providers={"gemini": lambda: 100.0},
    )
    review_agent = GuardrailReviewAgent(visible_store=store)
    resource_agent = ResourceMonitorAgent(visible_store=store)

    scheduler.register_agent(health_agent)
    scheduler.register_agent(review_agent)
    scheduler.register_agent(resource_agent)

    reports = scheduler.trigger_all()
    assert len(reports) == 3
    assert all(r.success for r in reports)

    logs = store.query_logs(limit=10)
    assert len(logs) >= 3


def test_background_scheduler_threaded_lifecycle():
    store = SQLiteAgentLogStore(":memory:")
    scheduler = BackgroundAgentScheduler(visible_store=store)

    counter = {"runs": 0}

    class MockAgent(ProviderHealthAgent):
        def run_cycle(self):
            counter["runs"] += 1
            return super().run_cycle()

    mock_agent = MockAgent(visible_store=store, providers={"test": lambda: 50.0})
    scheduler.register_agent(mock_agent, interval_seconds=0.1)

    assert scheduler.is_running is False
    scheduler.start()
    assert scheduler.is_running is True

    # Sleep slightly to let thread cycle run
    time.sleep(0.35)

    scheduler.stop()
    assert scheduler.is_running is False
    assert counter["runs"] >= 2
    logs = store.query_logs()
    assert len(logs) >= 2
