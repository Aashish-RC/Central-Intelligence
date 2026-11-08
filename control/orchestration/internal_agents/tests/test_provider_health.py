"""Tests for ProviderHealthAgent."""

import time
import pytest
from internal_agents.core.models import AgentSeverity, AgentType
from internal_agents.storage.sqlite_agent_log import SQLiteAgentLogStore
from internal_agents.agents.provider_health import ProviderHealthAgent


@pytest.fixture
def log_store():
    return SQLiteAgentLogStore(":memory:")


def test_provider_health_nominal(log_store):
    def mock_fast_ping():
        return 120.0

    agent = ProviderHealthAgent(
        visible_store=log_store,
        providers={"gemini": mock_fast_ping},
        latency_threshold_ms=1000.0,
    )

    result = agent.check_provider("gemini")
    assert result.is_healthy is True
    assert result.latency_ms == 120.0
    assert result.error_message is None

    report = agent.run_cycle()
    assert report.success is True
    assert report.items_processed == 1
    assert report.anomalies_detected == 0

    logs = log_store.query_logs(agent_type=AgentType.PROVIDER_HEALTH)
    assert len(logs) == 1
    assert logs[0].severity == AgentSeverity.INFO
    assert "HEALTHY" in logs[0].message


def test_provider_health_latency_degraded(log_store):
    def mock_slow_ping():
        return 3500.0

    agent = ProviderHealthAgent(
        visible_store=log_store,
        providers={"openai": mock_slow_ping},
        latency_threshold_ms=2000.0,
    )

    result = agent.check_provider("openai")
    assert result.is_healthy is False
    assert "exceeded threshold" in (result.error_message or "")

    report = agent.run_cycle()
    assert report.anomalies_detected == 1

    logs = log_store.query_logs(agent_type=AgentType.PROVIDER_HEALTH)
    assert len(logs) == 1
    assert logs[0].severity == AgentSeverity.WARNING
    assert "DEGRADED" in logs[0].message


def test_provider_health_failure_exception(log_store):
    def mock_failing_ping():
        raise ConnectionResetError("Remote server closed connection")

    agent = ProviderHealthAgent(
        visible_store=log_store,
        providers={"anthropic": mock_failing_ping},
    )

    result = agent.check_provider("anthropic")
    assert result.is_healthy is False
    assert "Remote server closed connection" in (result.error_message or "")

    report = agent.run_cycle()
    assert report.anomalies_detected == 1

    logs = log_store.query_logs(agent_type=AgentType.PROVIDER_HEALTH)
    assert logs[0].severity == AgentSeverity.WARNING


def test_provider_health_unregistered_provider(log_store):
    agent = ProviderHealthAgent(visible_store=log_store)
    result = agent.check_provider("non_existent")
    assert result.is_healthy is False
    assert "not registered" in (result.error_message or "")
