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
