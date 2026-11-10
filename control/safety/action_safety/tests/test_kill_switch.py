"""
Tests for Emergency Agent Kill Switch (10.24)
Verifies sub-second halt latency, tenant/user scoping, state freezing, and cancellation.
"""

import time
import pytest
from control.safety.action_safety.kill_switch import (
    AgentHaltedError,
    AgentKillSwitch,
    KillSwitchScope,
)


@pytest.fixture
def kill_switch():
    return AgentKillSwitch()


def test_kill_switch_sub_second_latency(kill_switch):
    """Acceptance Test: Kill switch -> all agents stop within 1 second (< 10ms in-memory)."""
    t0 = time.perf_counter()
    event = kill_switch.trigger(
        tenant_id="tenant_perf",
        reason="Rapid containment required",
    )
    is_stopped = kill_switch.is_halted(tenant_id="tenant_perf")
    t1 = time.perf_counter()

    elapsed = t1 - t0
    assert elapsed < 1.0, f"Kill switch took {elapsed:.4f}s, expected < 1.0s"
    assert is_stopped is True
    assert event.scope == KillSwitchScope.TENANT


def test_tenant_and_user_scoping(kill_switch):
    # Trip kill switch for user_rogue in tenant_A only
    kill_switch.trigger(
        tenant_id="tenant_A",
        user_id="user_rogue",
        reason="Suspicious looping behavior",
    )

    # user_rogue in tenant_A must be halted
    assert kill_switch.is_halted(tenant_id="tenant_A", user_id="user_rogue") is True
    with pytest.raises(AgentHaltedError) as exc_info:
        kill_switch.assert_not_halted(tenant_id="tenant_A", user_id="user_rogue")
    assert "Suspicious looping behavior" in str(exc_info.value)

    # other users in tenant_A must NOT be halted
    assert kill_switch.is_halted(tenant_id="tenant_A", user_id="user_innocent") is False

    # tenant_B must NOT be halted
    assert kill_switch.is_halted(tenant_id="tenant_B", user_id="user_rogue") is False


def test_global_kill_switch(kill_switch):
    kill_switch.trigger(is_global=True, reason="System-wide security incident")
    assert kill_switch.is_halted(tenant_id="any_tenant", user_id="any_user") is True

    with pytest.raises(AgentHaltedError) as exc_info:
        kill_switch.assert_not_halted(tenant_id="tenant_123")
    assert "global" in str(exc_info.value).lower()


def test_state_freezing(kill_switch):
    current_state = {
        "step": 4,
        "tool": "database_migration",
        "pending_rows": 1500,
    }
    event = kill_switch.trigger(
        tenant_id="tenant_finance",
        current_state=current_state,
        reason="Anomalous table drop detected",
    )

    assert event.frozen_state["step"] == 4
    assert event.frozen_state["tool"] == "database_migration"
    assert "halted_at_timestamp" in event.frozen_state


def test_registered_task_cancellation(kill_switch):
    cancelled = []

    def task_cancel():
        cancelled.append("task_1_cancelled")

    kill_switch.register_cancellable(
        task_id="task_1",
        cancel_callback=task_cancel,
        tenant_id="tenant_cancel_test",
    )

    # Triggering for another tenant should not cancel
    kill_switch.trigger(tenant_id="other_tenant")
    assert len(cancelled) == 0

    # Triggering for target tenant cancels task immediately
    kill_switch.trigger(tenant_id="tenant_cancel_test")
    assert len(cancelled) == 1
    assert cancelled[0] == "task_1_cancelled"


def test_reset_kill_switch(kill_switch):
    kill_switch.trigger(tenant_id="tenant_reset")
    assert kill_switch.is_halted(tenant_id="tenant_reset") is True

    kill_switch.reset(tenant_id="tenant_reset")
    assert kill_switch.is_halted(tenant_id="tenant_reset") is False
