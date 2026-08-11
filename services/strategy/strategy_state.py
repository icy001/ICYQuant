"""
Strategy lifecycle states and transitions.

Defines the authoritative state machine for production strategy management,
from creation through validation, deployment, execution, and archival.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Set


class StrategyLifecycleState(str, Enum):
    """Production strategy lifecycle states."""

    CREATED = "CREATED"
    """Strategy has been created but not yet validated."""

    VALIDATING = "VALIDATING"
    """Strategy is undergoing validation checks."""

    VALIDATED = "VALIDATED"
    """Strategy has passed all validation checks."""

    REGISTERING = "REGISTERING"
    """Strategy is being registered into the platform."""

    REGISTERED = "REGISTERED"
    """Strategy is registered but not yet deployed."""

    DEPLOYING = "DEPLOYING"
    """Strategy is being deployed to the runtime."""

    DEPLOYED = "DEPLOYED"
    """Strategy is deployed but not yet running."""

    STARTING = "STARTING"
    """Strategy is starting up."""

    RUNNING = "RUNNING"
    """Strategy is actively running."""

    PAUSING = "PAUSING"
    """Strategy is being paused."""

    PAUSED = "PAUSED"
    """Strategy is temporarily paused."""

    RESUMING = "RESUMING"
    """Strategy is resuming from paused state."""

    STOPPING = "STOPPING"
    """Strategy is being stopped gracefully."""

    STOPPED = "STOPPED"
    """Strategy has been stopped."""

    DEGRADED = "DEGRADED"
    """Strategy is running in a degraded mode."""

    FAILED = "FAILED"
    """Strategy has encountered an unrecoverable error."""

    RECOVERING = "RECOVERING"
    """Strategy is attempting recovery from a failure."""

    ARCHIVING = "ARCHIVING"
    """Strategy is being archived."""

    ARCHIVED = "ARCHIVED"
    """Strategy has been archived and is no longer active."""


# ── State Transition Rules ──

VALID_TRANSITIONS: Dict[StrategyLifecycleState, Set[StrategyLifecycleState]] = {
    StrategyLifecycleState.CREATED: {
        StrategyLifecycleState.VALIDATING,
        StrategyLifecycleState.ARCHIVING,
    },
    StrategyLifecycleState.VALIDATING: {
        StrategyLifecycleState.VALIDATED,
        StrategyLifecycleState.FAILED,
    },
    StrategyLifecycleState.VALIDATED: {
        StrategyLifecycleState.REGISTERING,
        StrategyLifecycleState.FAILED,
    },
    StrategyLifecycleState.REGISTERING: {
        StrategyLifecycleState.REGISTERED,
        StrategyLifecycleState.FAILED,
    },
    StrategyLifecycleState.REGISTERED: {
        StrategyLifecycleState.DEPLOYING,
        StrategyLifecycleState.VALIDATING,
        StrategyLifecycleState.ARCHIVING,
    },
    StrategyLifecycleState.DEPLOYING: {
        StrategyLifecycleState.DEPLOYED,
        StrategyLifecycleState.FAILED,
    },
    StrategyLifecycleState.DEPLOYED: {
        StrategyLifecycleState.STARTING,
        StrategyLifecycleState.ARCHIVING,
    },
    StrategyLifecycleState.STARTING: {
        StrategyLifecycleState.RUNNING,
        StrategyLifecycleState.FAILED,
    },
    StrategyLifecycleState.RUNNING: {
        StrategyLifecycleState.PAUSING,
        StrategyLifecycleState.STOPPING,
        StrategyLifecycleState.DEGRADED,
        StrategyLifecycleState.FAILED,
    },
    StrategyLifecycleState.PAUSING: {
        StrategyLifecycleState.PAUSED,
        StrategyLifecycleState.FAILED,
    },
    StrategyLifecycleState.PAUSED: {
        StrategyLifecycleState.RESUMING,
        StrategyLifecycleState.STOPPING,
        StrategyLifecycleState.FAILED,
    },
    StrategyLifecycleState.RESUMING: {
        StrategyLifecycleState.RUNNING,
        StrategyLifecycleState.FAILED,
    },
    StrategyLifecycleState.STOPPING: {
        StrategyLifecycleState.STOPPED,
        StrategyLifecycleState.FAILED,
    },
    StrategyLifecycleState.STOPPED: {
        StrategyLifecycleState.STARTING,
        StrategyLifecycleState.ARCHIVING,
    },
    StrategyLifecycleState.DEGRADED: {
        StrategyLifecycleState.RUNNING,
        StrategyLifecycleState.RECOVERING,
        StrategyLifecycleState.STOPPING,
        StrategyLifecycleState.FAILED,
    },
    StrategyLifecycleState.FAILED: {
        StrategyLifecycleState.RECOVERING,
        StrategyLifecycleState.ARCHIVING,
    },
    StrategyLifecycleState.RECOVERING: {
        StrategyLifecycleState.RUNNING,
        StrategyLifecycleState.FAILED,
        StrategyLifecycleState.STOPPING,
    },
    StrategyLifecycleState.ARCHIVING: {
        StrategyLifecycleState.ARCHIVED,
        StrategyLifecycleState.FAILED,
    },
    StrategyLifecycleState.ARCHIVED: set(),
}


TERMINAL_STATES: Set[StrategyLifecycleState] = {
    StrategyLifecycleState.ARCHIVED,
}


ACTIVE_STATES: Set[StrategyLifecycleState] = {
    StrategyLifecycleState.RUNNING,
    StrategyLifecycleState.PAUSED,
    StrategyLifecycleState.DEGRADED,
    StrategyLifecycleState.RECOVERING,
}


@dataclass
class StateTransition:
    """Record of a lifecycle state transition."""

    strategy_id: str
    from_state: StrategyLifecycleState
    to_state: StrategyLifecycleState
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "reason": self.reason,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
        }


def can_transition(
    current: StrategyLifecycleState,
    target: StrategyLifecycleState,
) -> bool:
    """Check if a transition from current to target state is valid."""
    allowed = VALID_TRANSITIONS.get(current, set())
    return target in allowed


def is_active(state: StrategyLifecycleState) -> bool:
    """Check if the state represents an actively running strategy."""
    return state in ACTIVE_STATES


def is_terminal(state: StrategyLifecycleState) -> bool:
    """Check if the state is a terminal (end-of-life) state."""
    return state in TERMINAL_STATES
