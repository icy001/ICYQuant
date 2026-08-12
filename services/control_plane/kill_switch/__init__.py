"""Kill Switch — the highest-priority trading halt mechanism."""

from .kill_switch import (
    KillSwitch,
    KillSwitchActivation,
    KillSwitchActivationOutcome,
    KillSwitchEntry,
    KillSwitchRelease,
    KillSwitchReleaseOutcome,
)
from .kill_switch_reason import KillSwitchReason
from .kill_switch_scope import KillSwitchScope
from .kill_switch_state import KillSwitchState

__all__ = [
    "KillSwitch",
    "KillSwitchActivation",
    "KillSwitchActivationOutcome",
    "KillSwitchEntry",
    "KillSwitchReason",
    "KillSwitchRelease",
    "KillSwitchReleaseOutcome",
    "KillSwitchScope",
    "KillSwitchState",
]
