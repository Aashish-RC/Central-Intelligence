"""Tests for ResourceMonitorAgent."""

import pytest
from internal_agents.core.models import AgentSeverity, AgentType, ResourceMetric, utc_now
from internal_agents.storage.sqlite_agent_log import SQLiteAgentLogStore
from internal_agents.agents.resource_monitor import ResourceMonitorAgent


@pytest.fixture
def log_store():
    return SQLiteAgentLogStore(":memory:")


def test_resource_monitor_nominal(log_store):
    def nominal_sampler():
        return ResourceMetric(
            cpu_percent=25.0,
            ram_used_mb=2048.0,
            ram_percent=45.0,
            active_tasks=3,
            recorded_at=utc_now(),
        )

    agent = ResourceMonitorAgent(
        visible_store=log_store,
        sampler_fn=nominal_sampler,
        cpu_threshold_percent=85.0,
        ram_threshold_percent=90.0,
    )

    report = agent.run_cycle()
    assert report.success is True
    assert report.items_processed == 1
    assert report.anomalies_detected == 0

    logs = log_store.query_logs(agent_type=AgentType.RESOURCE_MONITOR)
    assert len(logs) == 1
    assert logs[0].severity == AgentSeverity.INFO
    assert logs[0].action == "telemetry_sample"


def test_resource_monitor_cpu_spike(log_store):
    def elevated_cpu_sampler():
        return ResourceMetric(
            cpu_percent=96.5,
            ram_used_mb=2048.0,
            ram_percent=45.0,
            active_tasks=8,
            recorded_at=utc_now(),
        )

    agent = ResourceMonitorAgent(
        visible_store=log_store,
        sampler_fn=elevated_cpu_sampler,
        cpu_threshold_percent=85.0,
    )

    report = agent.run_cycle()
    assert report.anomalies_detected == 1

    logs = log_store.query_logs(agent_type=AgentType.RESOURCE_MONITOR)
    actions = [l.action for l in logs]
    assert "cpu_threshold_exceeded" in actions


def test_resource_monitor_ram_spike(log_store):
    def elevated_ram_sampler():
        return ResourceMetric(
            cpu_percent=30.0,
            ram_used_mb=15800.0,
            ram_percent=98.2,
            active_tasks=5,
            recorded_at=utc_now(),
        )

    agent = ResourceMonitorAgent(
        visible_store=log_store,
        sampler_fn=elevated_ram_sampler,
        ram_threshold_percent=90.0,
    )

    report = agent.run_cycle()
    assert report.anomalies_detected == 1

    logs = log_store.query_logs(agent_type=AgentType.RESOURCE_MONITOR)
    actions = [l.action for l in logs]
    assert "ram_threshold_exceeded" in actions
