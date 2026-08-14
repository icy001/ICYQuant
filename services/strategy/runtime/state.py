"""Strategy runtime state.

``RuntimeState`` expresses what the strategy *process* is actually doing,
independently of the control state (which records what the operator asked
the strategy to do).  The two must be kept apart: a strategy can be
``PAUSED`` (control) while its runtime is still ``RUNNING`` because pausing
only disables signal generation.

Runtime states (spec Commit 30 Part 1.2)::

    UNKNOWN  INITIALIZING  READY  RUNNING  DEGRADED  STOPPING  STOPPED  FAILED
"""

from __future__ import annotations

from enum import Enum


class RuntimeState(str, Enum):
    """The observed state of a strategy runtime process."""

    UNKNOWN = "UNKNOWN"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


#: Runtime states in which the process is considered alive and useful.
ALIVE_STATES: frozenset[str] = frozenset(
    {
        RuntimeState.INITIALIZING,
        RuntimeState.READY,
        RuntimeState.RUNNING,
        RuntimeState.DEGRADED,
    }
)

#: Runtime states that are fully consistent with an active strategy.
HEALTHY_STATES: frozenset[str] = frozenset(
    {
        RuntimeState.READY,
        RuntimeState.RUNNING,
    }
)

#: Runtime states in which the system has no reliable information.
UNKNOWN_STATES: frozenset[str] = frozenset(
    {
        RuntimeState.UNKNOWN,
    }
)


def runtime_state_value(state: "str | RuntimeState") -> str:
    """Normalise ``state`` to its plain string value."""
    return state.value if isinstance(state, RuntimeState) else state
