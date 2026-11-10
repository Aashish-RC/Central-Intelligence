"""Test Suite for Uptime Kuma Health & Status Page Adapter.
(Layer 14: Features 14.13, 14.21)
"""

import pytest
from control.observability.uptime import ServiceStatus, UptimeKumaAdapter


@pytest.fixture
def kuma():
    return UptimeKumaAdapter()


def test_1_monitor_registration_and_healthy_ping(kuma):
    """Test 1: Service monitor can be registered and responds healthy."""
    mon = kuma.add_monitor("Reasoning Gateway", "http://localhost:3000/health")
    assert mon.status == ServiceStatus.OPERATIONAL

    # Ping with healthy mock
    res = kuma.ping_monitor(mon.monitor_id, custom_checker=lambda: (True, 15.4))
    assert res.status == ServiceStatus.OPERATIONAL
    assert res.last_ping_ms == 15.4
    assert res.uptime_percentage == 100.0


def test_2_transient_failure_marks_degraded(kuma):
    """Test 2: Single failure marks service as degraded before threshold."""
    mon = kuma.add_monitor("Vector Store", "http://localhost:6333", alert_threshold_failures=2)

    # 1st failure
    kuma.ping_monitor(mon.monitor_id, custom_checker=lambda: (False, 0.0))
    assert mon.status == ServiceStatus.DEGRADED
    assert mon.consecutive_failures == 1
    assert len(kuma._alert_log) == 0  # No alert dispatched yet


def test_3_threshold_failure_triggers_outage_alert(kuma):
    """Test 3: Consecutive failures hitting threshold dispatch outage alert (14.13)."""
    mon = kuma.add_monitor("OpenFGA ReBAC", "http://localhost:8081", alert_threshold_failures=2)

    # 1st failure -> degraded
    kuma.ping_monitor(mon.monitor_id, custom_checker=lambda: (False, 0.0))
    assert mon.status == ServiceStatus.DEGRADED

    # 2nd failure -> outage + alert
    kuma.ping_monitor(mon.monitor_id, custom_checker=lambda: (False, 0.0))
    assert mon.status == ServiceStatus.OUTAGE
    assert len(kuma._alert_log) == 1
    assert kuma._alert_log[0]["service_name"] == "OpenFGA ReBAC"
    assert len(kuma._incidents) == 1


def test_4_public_status_page(kuma):
    """Test 4: Status page displays overall state and active incidents (14.21)."""
    m1 = kuma.add_monitor("Auth Service", "http://localhost:8080")
    m2 = kuma.add_monitor("Database", "http://localhost:5432", alert_threshold_failures=1)

    # m1 healthy
    kuma.ping_monitor(m1.monitor_id, custom_checker=lambda: (True, 5.0))
    # m2 outage
    kuma.ping_monitor(m2.monitor_id, custom_checker=lambda: (False, 0.0))

    page = kuma.get_status_page()
    assert page["system_status"] == "outage"
    assert len(page["services"]) == 2
    assert len(page["active_incidents"]) == 1
    assert page["active_incidents"][0]["title"] == "Database is down"


def test_5_uptime_percentage_calculation(kuma):
    """Test 5: Uptime percentage correctly computes ratio of successful checks."""
    mon = kuma.add_monitor("Cache", "http://localhost:6379")

    # 3 success, 1 failure = 75%
    kuma.ping_monitor(mon.monitor_id, custom_checker=lambda: (True, 2.0))
    kuma.ping_monitor(mon.monitor_id, custom_checker=lambda: (True, 2.0))
    kuma.ping_monitor(mon.monitor_id, custom_checker=lambda: (True, 2.0))
    kuma.ping_monitor(mon.monitor_id, custom_checker=lambda: (False, 0.0))

    assert mon.uptime_percentage == 75.0
