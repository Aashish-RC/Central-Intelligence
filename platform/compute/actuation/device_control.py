"""Actuation & Device Control (L16 Compute - Tasks 16.29, 16.30).

Provides secure physical device actuation with confirmation gates, command
rate limits, state validation, and reversible state rollback.
"""

from __future__ import annotations

import collections
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CommandStatus(str, Enum):
    PENDING_CONFIRMATION = "pending_confirmation"
    APPROVED = "approved"
    EXECUTED = "executed"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeviceState:
    """Current state snapshot of physical/IoT device."""
    device_id: str
    name: str
    device_type: str  # e.g., "thermostat", "smart_plug", "industrial_valve"
    state: Dict[str, Any] = field(default_factory=dict)
    last_actuated_at: float = 0.0


@dataclass
class ActuationCommand:
    """A command issued to a physical device."""
    command_id: str
    device_id: str
    action: str
    parameters: Dict[str, Any]
    requires_confirmation: bool = True
    status: CommandStatus = CommandStatus.PENDING_CONFIRMATION
    previous_state: Dict[str, Any] = field(default_factory=dict)
    executed_state: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    executed_at: Optional[float] = None


class RateLimitExceededError(Exception):
    """Raised when actuation frequency exceeds safe thresholds."""
    pass


class ConfirmationRequiredError(Exception):
    """Raised when an actuation is attempted without passing the confirmation gate."""
    pass


class DeviceActuationController:
    """Controls physical device actuation with confirmation gates and rollback."""

    def __init__(self, max_commands_per_minute: int = 10) -> None:
        self.max_commands_per_minute = max_commands_per_minute
        self._devices: Dict[str, DeviceState] = {}
        self._commands: Dict[str, ActuationCommand] = {}
        # device_id -> list of timestamps
        self._rate_limit_history: Dict[str, collections.deque[float]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max_commands_per_minute)
        )

    def register_device(
        self,
        device_id: str,
        name: str,
        device_type: str,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> DeviceState:
        """Register a physical or simulated device."""
        device = DeviceState(
            device_id=device_id,
            name=name,
            device_type=device_type,
            state=dict(initial_state or {}),
        )
        self._devices[device_id] = device
        return device

    def get_device(self, device_id: str) -> Optional[DeviceState]:
        return self._devices.get(device_id)

    def _check_rate_limit(self, device_id: str) -> None:
        now = time.time()
        window_start = now - 60.0
        history = self._rate_limit_history[device_id]

        # Prune older than 60s
        while history and history[0] < window_start:
            history.popleft()

        if len(history) >= self.max_commands_per_minute:
            raise RateLimitExceededError(
                f"Actuation rate limit exceeded for device '{device_id}' (max {self.max_commands_per_minute}/min)"
            )

    def propose_command(
        self,
        device_id: str,
        action: str,
        parameters: Dict[str, Any],
        requires_confirmation: bool = True,
    ) -> ActuationCommand:
        """Propose an actuation command. If confirmation is required, remains pending."""
        if device_id not in self._devices:
            raise ValueError(f"Unknown device: {device_id}")

        command = ActuationCommand(
            command_id=f"cmd_{uuid.uuid4().hex[:10]}",
            device_id=device_id,
            action=action,
            parameters=parameters,
            requires_confirmation=requires_confirmation,
            status=CommandStatus.PENDING_CONFIRMATION if requires_confirmation else CommandStatus.APPROVED,
        )
        self._commands[command.command_id] = command
        return command

    def confirm_and_execute(
        self,
        command_id: str,
        confirmation_token: Optional[str] = None,
    ) -> ActuationCommand:
        """Confirm a pending command and execute it against physical device."""
        command = self._commands.get(command_id)
        if not command:
            raise ValueError(f"Command not found: {command_id}")

        if command.status == CommandStatus.EXECUTED:
            return command

        device = self._devices[command.device_id]
        self._check_rate_limit(command.device_id)

        # Confirmation gate
        if command.requires_confirmation:
            if not confirmation_token:
                raise ConfirmationRequiredError(
                    f"Action '{command.action}' on device '{command.device_id}' requires explicit confirmation token"
                )

        # Snapshot current state for rollback
        command.previous_state = dict(device.state)

        # Execute actuation (update device state)
        device.state.update(command.parameters)
        now = time.time()
        device.last_actuated_at = now
        self._rate_limit_history[command.device_id].append(now)

        command.executed_state = dict(device.state)
        command.status = CommandStatus.EXECUTED
        command.executed_at = now

        logger.info(
            "Executed command %s on %s: action=%s, new_state=%s",
            command.command_id,
            command.device_id,
            command.action,
            device.state,
        )
        return command

    def rollback(self, command_id: str) -> ActuationCommand:
        """Roll back an executed actuation to its previous state."""
        command = self._commands.get(command_id)
        if not command:
            raise ValueError(f"Command not found: {command_id}")

        if command.status != CommandStatus.EXECUTED:
            raise ValueError(f"Cannot rollback non-executed command: {command.status}")

        device = self._devices[command.device_id]
        self._check_rate_limit(command.device_id)

        # Revert state
        device.state = dict(command.previous_state)
        device.last_actuated_at = time.time()
        self._rate_limit_history[command.device_id].append(time.time())

        command.status = CommandStatus.ROLLED_BACK
        logger.info("Rolled back command %s on %s. Reverted to: %s", command_id, device.device_id, device.state)
        return command

    def get_command(self, command_id: str) -> Optional[ActuationCommand]:
        return self._commands.get(command_id)
