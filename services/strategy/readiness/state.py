"""Strategy execution readiness state.

The three states of a strategy are deliberately kept apart::

    Lifecycle state  - what the operator asked the strategy to do
    Runtime state    - what the strategy process is actually doing
    Readiness state  - whether the strategy may produce execution intents

A strategy can be ``RUNNING`` (lifecycle) and ``RUNNING`` (runtime) yet still
not be READY because, for example, market data is stale, the risk gate is
blocked or execution connectivity is down.  The execution readiness gate is
the last system-level barrier before signal generation.

The single most important rule::

    Strategy RUNNING != Strategy EXECUTION READY
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ExecutionReadiness(str, Enum):
    """Whether a strategy is allowed to enter the execution pipeline."""

    UNKNOWN = "UNKNOWN"
    NOT_READY = "NOT_READY"
    CHECKING = "CHECKING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


#: States that are executable on their own.  A DEGRADED strategy may still be
#: allowed to trade, but only when ``ReadinessPolicy.allow_degraded`` says so.
EXECUTABLE_STATES: frozenset[str] = frozenset({ExecutionReadiness.READY})


def readiness_state_value(state: "str | ExecutionReadiness") -> str:
    """Normalise a state value to its plain string form."""
    if isinstance(state, ExecutionReadiness):
        return state.value
    return state


def is_executable(state: "str | ExecutionReadiness") -> bool:
    """Return True when the readiness state alone permits execution."""
    return readiness_state_value(state) in EXECUTABLE_STATES


@dataclass(frozen=True)
class ReadinessContext:
    """A single logical-time snapshot consumed by every readiness check.

    All checks evaluate the exact same snapshot so that one readiness
    evaluation cannot mix states read at different moments (T1/T2/T3).
    """

    strategy_id: str
    control_state: str = "UNKNOWN"
    runtime_state: str = "UNKNOWN"
    market_data_state: str = "UNKNOWN"
    configuration_state: str = "UNKNOWN"
    risk_state: str = "UNKNOWN"
    execution_state: str = "UNKNOWN"
    timestamp: float = field(default_factory=time.time)
    evaluation_id: Optional[str] = None


_evaluation_counter = itertools.count(1)


def new_evaluation_id(timestamp: Optional[float] = None) -> str:
    """Generate a monotonically increasing readiness evaluation id.

    Example: ``READINESS-20260813-000001``.
    """
    reference = time.time() if timestamp is None else timestamp
    date_part = datetime.fromtimestamp(reference).strftime("%Y%m%d")
    sequence = next(_evaluation_counter)
    return f"READINESS-{date_part}-{sequence:06d}"
