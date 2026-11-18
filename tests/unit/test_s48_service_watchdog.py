"""Unit tests for Stage S4.8 Production Health Check & Self-Healing Watchdog."""

import time
import pytest
from platform_infra.compute.health.service_watchdog import (
    ServiceWatchdog,
    ServiceProbeConfig,
    ServiceHealthStatus,
    ServiceHealthRecord,
)


def test_watchdog_registration_and_initial_status():
    """Verify service probe registration initializes healthy record."""
    wd = ServiceWatchdog()
    wd.register_service(
        ServiceProbeConfig(service_name="postgres", probe_type="tcp", host="127.0.0.1", port=5432)
    )

    status = wd.get_service_status("postgres")
    assert status is not None
    assert status.service_name == "postgres"
    assert status.status == ServiceHealthStatus.HEALTHY
    assert status.total_probes == 0


def test_watchdog_custom_probe_success():
    """Verify custom probe success resets failure counters."""
    wd = ServiceWatchdog()
    wd.register_service(
        ServiceProbeConfig(
            service_name="mock_svc",
            probe_type="custom",
            custom_probe_fn=lambda: True,
        )
    )

    success = wd.probe_service("mock_svc")
    assert success is True
    rec = wd.get_service_status("mock_svc")
    assert rec.status == ServiceHealthStatus.HEALTHY
    assert rec.consecutive_successes == 1
    assert rec.consecutive_failures == 0
    assert rec.total_probes == 1


def test_watchdog_failure_threshold_and_state_transition():
    """Verify consecutive probe failures transition service from HEALTHY to UNHEALTHY."""
    wd = ServiceWatchdog(auto_heal_enabled=False)
    probe_state = {"healthy": False}

    wd.register_service(
        ServiceProbeConfig(
            service_name="failing_svc",
            probe_type="custom",
            failure_threshold=3,
            custom_probe_fn=lambda: probe_state["healthy"],
        )
    )

    # 1st failure: remains healthy but failure count increases
    wd.probe_service("failing_svc")
    rec = wd.get_service_status("failing_svc")
    assert rec.consecutive_failures == 1
    assert rec.status == ServiceHealthStatus.HEALTHY

    # 2nd failure
    wd.probe_service("failing_svc")
    assert rec.consecutive_failures == 2
    assert rec.status == ServiceHealthStatus.HEALTHY

    # 3rd failure: reaches failure_threshold -> transitions to UNHEALTHY
    wd.probe_service("failing_svc")
    assert rec.consecutive_failures == 3
    assert rec.status == ServiceHealthStatus.UNHEALTHY


def test_watchdog_auto_healing_invocation_and_recovery():
    """Verify automated self-healing triggers remediation and restores healthy state."""
    heal_called = []
    service_alive = [False]

    def heal_hook():
        heal_called.append(True)
        service_alive[0] = True
        return True

    wd = ServiceWatchdog(auto_heal_enabled=True)
    wd.register_service(
        ServiceProbeConfig(
            service_name="auto_heal_svc",
            probe_type="custom",
            failure_threshold=2,
            recovery_threshold=2,
            healing_cooldown_s=5.0,
            custom_probe_fn=lambda: service_alive[0],
            custom_healing_fn=heal_hook,
        )
    )

    # 1st failure
    wd.probe_service("auto_heal_svc")
    assert len(heal_called) == 0

    # 2nd failure -> triggers self-healing
    wd.probe_service("auto_heal_svc")
    assert len(heal_called) == 1
    rec = wd.get_service_status("auto_heal_svc")
    assert rec.healing_attempts == 1

    # Next probe succeeds -> transitions to DEGRADED (1/2 recovery threshold)
    wd.probe_service("auto_heal_svc")
    assert rec.status == ServiceHealthStatus.DEGRADED
    assert rec.consecutive_successes == 1

    # Second successful probe -> transitions to HEALTHY (2/2 recovery threshold)
    wd.probe_service("auto_heal_svc")
    assert rec.status == ServiceHealthStatus.HEALTHY
    assert rec.consecutive_successes == 2

    # Verify incident logs
    incidents = wd.get_incident_log()
    events = [inc["event"] for inc in incidents]
    assert "HEALING_STARTED" in events
    assert "HEALING_DISPATCHED" in events
    assert "RECOVERED" in events


def test_watchdog_healing_cooldown_and_anti_flapping():
    """Verify watchdog enforces cooldown period before attempting another remediation."""
    heal_count = [0]

    def failing_heal():
        heal_count[0] += 1
        return True

    wd = ServiceWatchdog(auto_heal_enabled=True)
    wd.register_service(
        ServiceProbeConfig(
            service_name="flapping_svc",
            probe_type="custom",
            failure_threshold=1,
            healing_cooldown_s=60.0,  # 60s cooldown
            custom_probe_fn=lambda: False,
            custom_healing_fn=failing_heal,
        )
    )

    # 1st failure triggers heal
    wd.probe_service("flapping_svc")
    assert heal_count[0] == 1

    # Immediate next failure should NOT trigger another heal because of cooldown
    wd.probe_service("flapping_svc")
    assert heal_count[0] == 1


def test_watchdog_failed_healing_activates_fallback():
    """Verify failed healing intervention transitions service to FAILED and activates fallback."""
    def failed_heal():
        return False  # Remediation failed

    wd = ServiceWatchdog(auto_heal_enabled=True)
    wd.register_service(
        ServiceProbeConfig(
            service_name="unrecoverable_svc",
            probe_type="custom",
            failure_threshold=1,
            healing_cooldown_s=0.0,
            custom_probe_fn=lambda: False,
            custom_healing_fn=failed_heal,
        )
    )

    wd.probe_service("unrecoverable_svc")
    rec = wd.get_service_status("unrecoverable_svc")
    assert rec.status == ServiceHealthStatus.FAILED
    assert rec.fallback_active is True

    # Verify incident log contains FALLBACK_ACTIVATED
    incidents = wd.get_incident_log()
    events = [inc["event"] for inc in incidents]
    assert "FALLBACK_ACTIVATED" in events
