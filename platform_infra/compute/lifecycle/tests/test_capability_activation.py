"""Unit & Integration tests for Governed Capability-Driven Dynamic Activation Engine."""

import threading
import time
import pytest

from platform_infra.compute.lifecycle.capability_activation import (
    CapabilityActivationManager,
    CapabilityDefinition,
    CapabilityState,
    InsufficientResourceError,
    CapabilityDependencyError,
)


def test_default_capabilities_registered_and_rings():
    """Verify default core capabilities are registered with correct rings and states."""
    mgr = CapabilityActivationManager(max_total_memory_mb=4096)
    status = mgr.get_status()

    assert "relational_state" in status["capabilities"]
    assert "ephemeral_cache" in status["capabilities"]
    assert "vector_ann_search" in status["capabilities"]
    assert "knowledge_graph" in status["capabilities"]
    assert "rebac_authorization" in status["capabilities"]
    assert "durable_orchestration" in status["capabilities"]

    # Always-on critical services start active
    assert status["capabilities"]["relational_state"]["state"] == CapabilityState.ACTIVE
    assert status["capabilities"]["ephemeral_cache"]["state"] == CapabilityState.ACTIVE
    assert status["capabilities"]["durable_orchestration"]["state"] == CapabilityState.ACTIVE

    # On-demand services start inactive
    assert status["capabilities"]["vector_ann_search"]["state"] == CapabilityState.INACTIVE
    assert status["capabilities"]["knowledge_graph"]["state"] == CapabilityState.INACTIVE


def test_dependency_chain_auto_activation():
    """Verify activating a dependent capability auto-activates all required upstream capabilities."""
    mgr = CapabilityActivationManager(max_total_memory_mb=4096)

    # Initially vector search is inactive
    status = mgr.get_status()
    assert status["capabilities"]["vector_ann_search"]["state"] == CapabilityState.INACTIVE

    # Activate vector search (depends on relational_state)
    activated = mgr.activate_capability("vector_ann_search", caller_tenant="tenant_1")
    assert activated is True

    status = mgr.get_status()
    assert status["capabilities"]["vector_ann_search"]["state"] == CapabilityState.ACTIVE
    assert status["capabilities"]["relational_state"]["state"] == CapabilityState.ACTIVE


def test_memory_budget_enforcement_and_insufficient_resource_error():
    """Verify that activating capabilities beyond the memory ceiling raises InsufficientResourceError."""
    # Set ceiling low so that base active capabilities take most, and new one exceeds
    mgr = CapabilityActivationManager(max_total_memory_mb=900)
    # Default active: relational_state(512) + ephemeral_cache(64) + durable_orchestration(256) = 832 MB

    # Register a heavy capability requiring 200 MB
    mgr.register_capability(
        CapabilityDefinition(
            name="heavy_analytics",
            ring=2,
            required_services=["clickhouse"],
            memory_budget_mb=200,
        )
    )

    with pytest.raises(InsufficientResourceError, match="Cannot activate 'heavy_analytics'"):
        mgr.activate_capability("heavy_analytics")


def test_lease_acquisition_and_active_protection():
    """Verify lease acquisition activates capability and increments active leases."""
    mgr = CapabilityActivationManager(max_total_memory_mb=4096)

    lease = mgr.acquire_lease("knowledge_graph", tenant_id="tenant_alpha", workflow_id="wf_101")
    assert lease.active is True
    assert lease.capability_name == "knowledge_graph"
    assert lease.tenant_id == "tenant_alpha"

    status = mgr.get_status()
    assert status["capabilities"]["knowledge_graph"]["state"] == CapabilityState.ACTIVE
    assert status["capabilities"]["knowledge_graph"]["active_leases"] == 1


def test_lease_release_and_tenant_accounting():
    """Verify releasing a lease updates runtime seconds and peak concurrent counts."""
    mgr = CapabilityActivationManager(max_total_memory_mb=4096)

    lease1 = mgr.acquire_lease("knowledge_graph", tenant_id="tenant_beta")
    lease2 = mgr.acquire_lease("knowledge_graph", tenant_id="tenant_beta")

    time.sleep(0.05)
    mgr.release_lease(lease1.lease_id)
    mgr.release_lease(lease2.lease_id)

    status = mgr.get_status()
    assert status["capabilities"]["knowledge_graph"]["active_leases"] == 0

    accounting = mgr.get_tenant_accounting("tenant_beta")
    assert len(accounting) == 1
    record = accounting[0]
    assert record["capability"] == "knowledge_graph"
    assert record["total_leases"] == 2
    assert record["peak_concurrent_leases"] == 2
    assert record["runtime_seconds"] > 0.04


def test_active_workflow_protection_blocks_idle_shutdown():
    """Verify that a capability with an active lease is NEVER stopped during idle scan."""
    mgr = CapabilityActivationManager(max_total_memory_mb=4096)
    lease = mgr.acquire_lease("knowledge_graph", tenant_id="tenant_gamma")

    # Force simulated time past timeout
    simulated_future = time.time() + 1000.0
    drained = mgr.drain_idle_capabilities(now=simulated_future)

    # Should NOT drain because lease is still active
    assert "knowledge_graph" not in drained
    status = mgr.get_status()
    assert status["capabilities"]["knowledge_graph"]["state"] == CapabilityState.ACTIVE

    # Now release lease and re-run drain
    mgr.release_lease(lease.lease_id)
    drained_after = mgr.drain_idle_capabilities(now=simulated_future)
    assert "knowledge_graph" in drained_after
    status_after = mgr.get_status()
    assert status_after["capabilities"]["knowledge_graph"]["state"] == CapabilityState.INACTIVE


def test_durability_critical_services_never_stopped():
    """Verify that durability-critical capabilities (relational_state, durable_orchestration) are immune to idle shutdown."""
    mgr = CapabilityActivationManager(max_total_memory_mb=4096)
    simulated_future = time.time() + 10000.0

    drained = mgr.drain_idle_capabilities(now=simulated_future)
    assert "relational_state" not in drained
    assert "ephemeral_cache" not in drained
    assert "durable_orchestration" not in drained

    status = mgr.get_status()
    assert status["capabilities"]["relational_state"]["state"] == CapabilityState.ACTIVE
    assert status["capabilities"]["durable_orchestration"]["state"] == CapabilityState.ACTIVE


def test_state_preservation_hook_called_during_shutdown():
    """Verify that capability state_preservation_fn is executed prior to deactivation."""
    hook_called = False

    def on_preservation():
        nonlocal hook_called
        hook_called = True
        return True

    mgr = CapabilityActivationManager(max_total_memory_mb=4096)
    mgr.register_capability(
        CapabilityDefinition(
            name="ephemeral_work_scratchpad",
            ring=2,
            required_services=["scratchpad"],
            idle_timeout_seconds=10.0,
            state_preservation_fn=on_preservation,
        )
    )

    mgr.activate_capability("ephemeral_work_scratchpad")
    assert hook_called is False

    # Advance time past 10s and drain
    mgr.drain_idle_capabilities(now=time.time() + 20.0)
    assert hook_called is True
    assert mgr.get_status()["capabilities"]["ephemeral_work_scratchpad"]["state"] == CapabilityState.INACTIVE


def test_health_check_failure_blocks_activation():
    """Verify that failing health check marks capability FAILED and returns False."""
    mgr = CapabilityActivationManager(max_total_memory_mb=4096)
    mgr.register_capability(
        CapabilityDefinition(
            name="unhealthy_service",
            ring=2,
            required_services=["broken_node"],
            health_check_fn=lambda: False,
        )
    )

    result = mgr.activate_capability("unhealthy_service")
    assert result is False
    assert mgr.get_status()["capabilities"]["unhealthy_service"]["state"] == CapabilityState.FAILED


def test_thread_safe_concurrent_lease_acquisition():
    """Verify concurrent thread safety under multiple worker threads."""
    mgr = CapabilityActivationManager(max_total_memory_mb=4096)
    errors = []

    def worker_task(thread_idx: int):
        try:
            for _ in range(20):
                lease = mgr.acquire_lease("rebac_authorization", tenant_id=f"tenant_{thread_idx}")
                time.sleep(0.001)
                mgr.release_lease(lease.lease_id)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    status = mgr.get_status()
    assert status["capabilities"]["rebac_authorization"]["active_leases"] == 0
    # Audit trail recorded all lease activations
    assert status["audit_records_count"] > 100


# =============================================================================
# Phase B: Rigorous Regression Suite for Capability Activation Engine
# =============================================================================

def test_phase_b_01_real_service_activation_through_runtime_adapter():
    """Verify real service activation calls runtime adapter start/stop/health."""
    from platform_infra.compute.lifecycle.capability_activation import SimulatedRuntimeAdapter

    adapter = SimulatedRuntimeAdapter()
    mgr = CapabilityActivationManager(max_total_memory_mb=4096, runtime_adapter=adapter)

    # Register capability requiring custom services
    mgr.register_capability(
        CapabilityDefinition(
            name="custom_worker",
            ring=3,
            required_services=["worker_daemon_1", "worker_daemon_2"],
            memory_budget_mb=128,
            allows_idle_shutdown=True,
            idle_timeout_seconds=5.0,
        )
    )

    # Under runtime adapter, services should be started when activated
    assert not adapter.is_service_healthy("worker_daemon_1")
    mgr.activate_capability("custom_worker")
    assert adapter.is_service_healthy("worker_daemon_1")
    assert adapter.is_service_healthy("worker_daemon_2")

    # When drained, services should be stopped
    mgr.drain_idle_capabilities(now=time.time() + 10.0)
    assert not adapter.is_service_healthy("worker_daemon_1")
    assert not adapter.is_service_healthy("worker_daemon_2")


def test_phase_b_02_accurate_readiness_and_health_states():
    """Verify distinct readiness check and active health check monitoring."""
    from platform_infra.compute.lifecycle.capability_activation import SimulatedRuntimeAdapter

    readiness_calls = 0
    health_calls = 0

    def readiness_probe():
        nonlocal readiness_calls
        readiness_calls += 1
        return True

    def health_probe():
        nonlocal health_calls
        health_calls += 1
        return health_calls < 3  # passes initially, fails later

    mgr = CapabilityActivationManager(max_total_memory_mb=4096)
    mgr.register_capability(
        CapabilityDefinition(
            name="monitored_service",
            ring=2,
            required_services=["monitored_node"],
            readiness_check_fn=readiness_probe,
            health_check_fn=health_probe,
        )
    )

    mgr.activate_capability("monitored_service")
    assert readiness_calls == 1
    assert mgr.get_status()["capabilities"]["monitored_service"]["state"] == CapabilityState.ACTIVE

    # Check health actively
    assert mgr.check_capability_health("monitored_service") is True
    # Third call fails health check
    assert mgr.check_capability_health("monitored_service") is False
    assert mgr.get_status()["capabilities"]["monitored_service"]["state"] == CapabilityState.UNHEALTHY


def test_phase_b_03_lease_acquisition_failure_handling():
    """Verify acquire_lease raises CapabilityActivationError when capability fails activation."""
    from platform_infra.compute.lifecycle.capability_activation import CapabilityActivationError

    mgr = CapabilityActivationManager(max_total_memory_mb=4096)
    mgr.register_capability(
        CapabilityDefinition(
            name="broken_service",
            ring=2,
            required_services=["broken_node"],
            health_check_fn=lambda: False,
        )
    )

    with pytest.raises(CapabilityActivationError, match="activation failed"):
        mgr.acquire_lease("broken_service", tenant_id="tenant_x")


def test_phase_b_04_safe_shutdown_when_state_preservation_fails():
    """Verify capability shutdown is ABORTED when state preservation hook raises or fails."""
    preservation_attempted = False

    def failing_preservation():
        nonlocal preservation_attempted
        preservation_attempted = True
        raise IOError("Disk full: cannot persist state snapshot")

    mgr = CapabilityActivationManager(max_total_memory_mb=4096)
    mgr.register_capability(
        CapabilityDefinition(
            name="stateful_cache",
            ring=1,
            required_services=["cache_node"],
            idle_timeout_seconds=5.0,
            state_preservation_fn=failing_preservation,
        )
    )

    mgr.activate_capability("stateful_cache")
    assert mgr.get_status()["capabilities"]["stateful_cache"]["state"] == CapabilityState.ACTIVE

    # Attempt to drain idle
    drained = mgr.drain_idle_capabilities(now=time.time() + 10.0)
    assert preservation_attempted is True
    # Shutdown MUST be aborted to prevent data loss; capability remains ACTIVE
    assert "stateful_cache" not in drained
    assert mgr.get_status()["capabilities"]["stateful_cache"]["state"] == CapabilityState.ACTIVE


def test_phase_b_05_dependency_cycle_detection():
    """Verify dependency cycle detection at registration and activation."""
    mgr = CapabilityActivationManager(max_total_memory_mb=4096)

    # 1. Self cycle
    with pytest.raises(CapabilityDependencyError, match="Self dependency cycle"):
        mgr.register_capability(
            CapabilityDefinition(
                name="cyclic_self",
                ring=1,
                required_services=["svc_1"],
                dependencies=["cyclic_self"],
            )
        )

    # 2. Indirect cycle: cap_a -> cap_b -> cap_a
    mgr.register_capability(
        CapabilityDefinition(
            name="cap_a",
            ring=1,
            required_services=["svc_a"],
            dependencies=[],
        )
    )
    mgr.register_capability(
        CapabilityDefinition(
            name="cap_b",
            ring=1,
            required_services=["svc_b"],
            dependencies=["cap_a"],
        )
    )
    with pytest.raises(CapabilityDependencyError, match="Dependency cycle detected"):
        mgr.register_capability(
            CapabilityDefinition(
                name="cap_c_cyclic",
                ring=1,
                required_services=["svc_c"],
                dependencies=["cap_b", "cap_a"],
            )
        )
        # Trying to update or register circular cap_a dependency
        mgr.register_capability(
            CapabilityDefinition(
                name="cap_a",
                ring=1,
                required_services=["svc_a"],
                dependencies=["cap_b"],
            )
        )


def test_phase_b_06_protection_of_active_dependent_capabilities():
    """Verify an idle upstream capability is protected from draining if active downstream depends on it."""
    mgr = CapabilityActivationManager(max_total_memory_mb=4096)

    mgr.register_capability(
        CapabilityDefinition(
            name="upstream_base",
            ring=1,
            required_services=["base_svc"],
            dependencies=[],
            idle_timeout_seconds=5.0,
            allows_idle_shutdown=True,
        )
    )
    mgr.register_capability(
        CapabilityDefinition(
            name="downstream_consumer",
            ring=2,
            required_services=["consumer_svc"],
            dependencies=["upstream_base"],
            idle_timeout_seconds=60.0,
            allows_idle_shutdown=True,
        )
    )

    # Acquire lease on downstream consumer (auto-activates upstream_base)
    lease = mgr.acquire_lease("downstream_consumer", tenant_id="tenant_1")
    assert mgr.get_status()["capabilities"]["upstream_base"]["state"] == CapabilityState.ACTIVE
    assert mgr.get_status()["capabilities"]["downstream_consumer"]["state"] == CapabilityState.ACTIVE

    # Now simulate time past upstream_base's idle timeout (5s) but within downstream's
    simulated_now = time.time() + 10.0
    drained = mgr.drain_idle_capabilities(now=simulated_now)

    # upstream_base has 0 direct leases, but downstream_consumer depends on it and is ACTIVE
    assert "upstream_base" not in drained
    assert mgr.get_status()["capabilities"]["upstream_base"]["state"] == CapabilityState.ACTIVE

    # Once downstream lease is released and both time out, both can drain
    mgr.release_lease(lease.lease_id)
    drained_later = mgr.drain_idle_capabilities(now=time.time() + 100.0)
    assert "downstream_consumer" in drained_later
    assert "upstream_base" in drained_later


def test_phase_b_07_resource_accounting_against_actual_host_limits():
    """Verify memory ceiling detection and accounting against system limits."""
    from platform_infra.compute.lifecycle.capability_activation import detect_system_memory_limit_mb

    detected = detect_system_memory_limit_mb()
    assert detected >= 256

    mgr = CapabilityActivationManager()
    status = mgr.get_status()
    assert status["system_detected_memory_mb"] == detected
    assert status["max_memory_mb"] >= 256
    assert status["headroom_mb"] <= status["max_memory_mb"]


def test_phase_b_08_durable_lifecycle_auditing_and_tamper_evidence(tmp_path):
    """Verify durable JSONL audit trail persistence and SHA-256 Merkle chain verification."""
    audit_file = str(tmp_path / "capability_audit.jsonl")
    mgr = CapabilityActivationManager(max_total_memory_mb=4096, audit_log_path=audit_file)

    mgr.activate_capability("vector_ann_search", caller_tenant="tenant_sec", reason="Security audit check")
    lease = mgr.acquire_lease("vector_ann_search", tenant_id="tenant_sec")
    mgr.release_lease(lease.lease_id)

    # Verify cryptographic integrity of hash chain
    assert mgr.verify_audit_log_integrity() is True

    # Verify durable file was written and contains valid records
    with open(audit_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) >= 3

    # Tamper with an audit record in-memory and verify integrity check detects it
    mgr._audit_trail[0].reason = "TAMPERED_REASON"
    assert mgr.verify_audit_log_integrity() is False


def test_phase_b_09_restart_and_partial_failure_recovery():
    """Verify partial activation rollback and restart recovery."""
    from platform_infra.compute.lifecycle.capability_activation import SimulatedRuntimeAdapter

    adapter = SimulatedRuntimeAdapter()
    mgr = CapabilityActivationManager(max_total_memory_mb=4096, runtime_adapter=adapter)

    # Define a chain: parent -> dep1 (healthy) and dep2 (fails)
    mgr.register_capability(
        CapabilityDefinition(
            name="dep_healthy",
            ring=1,
            required_services=["svc_healthy"],
            dependencies=[],
            allows_idle_shutdown=True,
        )
    )
    mgr.register_capability(
        CapabilityDefinition(
            name="dep_failing",
            ring=1,
            required_services=["svc_failing"],
            dependencies=[],
            health_check_fn=lambda: False,
        )
    )
    mgr.register_capability(
        CapabilityDefinition(
            name="parent_cap",
            ring=2,
            required_services=["svc_parent"],
            dependencies=["dep_healthy", "dep_failing"],
        )
    )

    with pytest.raises(Exception):
        mgr.activate_capability("parent_cap")

    # dep_healthy should have been rolled back since parent_cap failed
    assert mgr.get_status()["capabilities"]["dep_healthy"]["state"] == CapabilityState.INACTIVE

    # Test recovery procedure
    recovery = mgr.recover_state()
    assert "relational_state" in recovery["recovered"]
    assert "ephemeral_cache" in recovery["recovered"]
    assert "durable_orchestration" in recovery["recovered"]


def test_phase_b_10_concurrent_activation_and_shutdown_behavior():
    """Verify concurrent activation and draining race does not deadlock or corrupt state."""
    mgr = CapabilityActivationManager(max_total_memory_mb=4096)
    errors = []

    def activator():
        try:
            for _ in range(15):
                mgr.activate_capability("knowledge_graph", caller_tenant="worker_t")
                time.sleep(0.002)
        except Exception as e:
            errors.append(e)

    def drainer():
        try:
            for _ in range(15):
                mgr.drain_idle_capabilities()
                time.sleep(0.002)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=activator) for _ in range(5)] + [
        threading.Thread(target=drainer) for _ in range(3)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert mgr.verify_audit_log_integrity() is True

