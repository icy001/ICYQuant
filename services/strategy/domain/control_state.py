"""Strategy control state.

``StrategyControlState`` expresses the position of a strategy inside the
institutional control boundary.  It is deliberately kept separate from
the runtime/process state: a strategy can be ``PAUSED`` (control state)
while its runtime process is still alive (``RUNNING`` in runtime terms)
because "paused" only blocks signal generation, not the runtime itself.

Control state answers "what did the operator ask the strategy to do",
runtime state answers "what is the strategy process actually doing".
"""

from __future__ import annotations

from enum import Enum


class StrategyControlState(str, Enum):
    """Lifecycle of a strategy as seen through its control commands."""

    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"

    PAUSING = "PAUSING"
    PAUSED = "PAUSED"

    RESUMING = "RESUMING"

    STOPPING = "STOPPING"
    KILLED = "KILLED"

    FAILED = "FAILED"


ACTIVE_STATES: frozenset[str] = frozenset(
    {
        StrategyControlState.STARTING,
        StrategyControlState.RUNNING,
        StrategyControlState.PAUSING,
        StrategyControlState.PAUSED,
        StrategyControlState.RESUMING,
        StrategyControlState.STOPPING,
    }
)

TERMINAL_STATES: frozenset[str] = frozenset(
    {
        StrategyControlState.STOPPED,
        StrategyControlState.KILLED,
        StrategyControlState.FAILED,
    }
)


def is_active(state: "str | StrategyControlState") -> bool:
    """Return True when the strategy is in a non-terminal, active state."""
    value = state.value if isinstance(state, StrategyControlState) else state
    return value in ACTIVE_STATES


def is_terminal(state: "str | StrategyControlState") -> bool:
    """Return True when the strategy reached a terminal control state."""
    value = state.value if isinstance(state, StrategyControlState) else state
    return value in TERMINAL_STATES
