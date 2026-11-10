"""
Action safety package.
"""

from .kill_switch import (
    AgentHaltedError,
    AgentKillSwitch,
    KillSwitchEvent,
    KillSwitchScope,
    default_kill_switch,
)

__all__ = [
    "AgentHaltedError",
    "AgentKillSwitch",
    "KillSwitchEvent",
    "KillSwitchScope",
    "default_kill_switch",
]
