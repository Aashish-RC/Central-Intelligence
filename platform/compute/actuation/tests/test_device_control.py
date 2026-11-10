"""Unit tests for DeviceActuationController (Task 16.6)."""

import pytest
from platform.compute.actuation.device_control import (
    DeviceActuationController,
    CommandStatus,
    ConfirmationRequiredError,
    RateLimitExceededError,
)


@pytest.fixture
def controller():
    return DeviceActuationController(max_commands_per_minute=5)


def test_iot_command_with_confirmation_gate(controller: DeviceActuationController):
    """Acceptance test: Can send IoT command with confirmation gate."""
    # Register industrial smart valve
    controller.register_device(
        device_id="valve_cooling_01",
        name="Reactor Cooling Valve",
        device_type="industrial_valve",
        initial_state={"open_pct": 20, "pressure_psi": 85},
    )

    # Propose command requiring confirmation
    cmd = controller.propose_command(
        device_id="valve_cooling_01",
        action="set_cooling_flow",
        parameters={"open_pct": 80},
        requires_confirmation=True,
    )
    assert cmd.status == CommandStatus.PENDING_CONFIRMATION

    # Attempting to execute without confirmation token fails gate
    with pytest.raises(ConfirmationRequiredError, match="requires explicit confirmation token"):
        controller.confirm_and_execute(cmd.command_id, confirmation_token=None)

    # Provide confirmation token -> passes gate and executes
    executed = controller.confirm_and_execute(cmd.command_id, confirmation_token="TOKEN_AUTH_1234")
    assert executed.status == CommandStatus.EXECUTED
    assert executed.previous_state == {"open_pct": 20, "pressure_psi": 85}
    assert executed.executed_state["open_pct"] == 80

    # Device state is updated
    device = controller.get_device("valve_cooling_01")
    assert device is not None
    assert device.state["open_pct"] == 80


def test_actuation_rollback(controller: DeviceActuationController):
    """Executed actuation can be rolled back to restore previous hardware state."""
    controller.register_device(
        device_id="smart_thermostat",
        name="HVAC Living Room",
        device_type="thermostat",
        initial_state={"target_temp_c": 21.0, "mode": "eco"},
    )

    cmd = controller.propose_command(
        device_id="smart_thermostat",
        action="boost_heat",
        parameters={"target_temp_c": 27.0, "mode": "boost"},
        requires_confirmation=True,
    )
    controller.confirm_and_execute(cmd.command_id, confirmation_token="OK_APPROVE")

    # State is now 27.0
    device = controller.get_device("smart_thermostat")
    assert device.state["target_temp_c"] == 27.0

    # Trigger rollback
    rolled_back = controller.rollback(cmd.command_id)
    assert rolled_back.status == CommandStatus.ROLLED_BACK
    assert device.state["target_temp_c"] == 21.0
    assert device.state["mode"] == "eco"


def test_actuation_rate_limiter(controller: DeviceActuationController):
    """Commands exceeding frequency limit are rejected to protect hardware."""
    controller.register_device("toggle_relay", "Power Relay", "relay", {"power": "off"})

    for i in range(5):
        cmd = controller.propose_command("toggle_relay", "power_on", {"power": f"on_{i}"}, requires_confirmation=False)
        controller.confirm_and_execute(cmd.command_id)

    # 6th command in the same minute exceeds limit
    cmd_exceeded = controller.propose_command("toggle_relay", "power_on", {"power": "on_6"}, requires_confirmation=False)
    with pytest.raises(RateLimitExceededError, match="Actuation rate limit exceeded"):
        controller.confirm_and_execute(cmd_exceeded.command_id)
