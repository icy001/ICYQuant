"""Execution State — Execution status enums and state tracking.

Defines the execution lifecycle states for both parent and child orders.
The state machine ensures valid transitions throughout the execution process.

States:
    PENDING → SUBMITTING → ACTIVE → COMPLETING → COMPLETED
                    ↓            ↓
               CANCELLING     PAUSED
                    ↓            ↓
               CANCELLED     RESUMING → ACTIVE
                    ↓
               REJECTED → ERROR

Usage::

    status = ExecutionStatus.ACTIVE
    if status.is_terminal:
        ...
"""

from __future__ import annotations

from enum import Enum


class ExecutionStatus(str, Enum):
    """Execution lifecycle status for parent and child orders.

    Lifecycle:
        PENDING: Created but not yet scheduled
        SUBMITTING: Being dispatched to broker
        ACTIVE: Currently executing in the market
        PAUSED: Temporarily suspended (algorithmic pause)
        RESUMING: Transitioning from paused to active
        COMPLETING: Final fill stage, wrapping up
        COMPLETED: Fully executed
        CANCELLING: Cancellation in progress
        CANCELLED: Cancelled before completion
        REJECTED: Rejected by broker or venue
        ERROR: System error during execution
    """

    PENDING = "PENDING"
    SUBMITTING = "SUBMITTING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    RESUMING = "RESUMING"
    COMPLETING = "COMPLETING"
    COMPLETED = "COMPLETED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"

    @property
    def is_terminal(self) -> bool:
        """Whether this status represents a terminal (final) state."""
        return self in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.REJECTED,
            ExecutionStatus.ERROR,
        )

    @property
    def is_active(self) -> bool:
        """Whether the execution is actively trading."""
        return self in (
            ExecutionStatus.SUBMITTING,
            ExecutionStatus.ACTIVE,
            ExecutionStatus.RESUMING,
        )

    @property
    def is_pausable(self) -> bool:
        """Whether execution can be paused from this state."""
        return self == ExecutionStatus.ACTIVE

    @property
    def is_cancellable(self) -> bool:
        """Whether execution can be cancelled from this state."""
        return self in (
            ExecutionStatus.PENDING,
            ExecutionStatus.SUBMITTING,
            ExecutionStatus.ACTIVE,
            ExecutionStatus.PAUSED,
        )


# Valid state transitions for the execution FSM
VALID_TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    ExecutionStatus.PENDING: {
        ExecutionStatus.SUBMITTING,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.ERROR,
    },
    ExecutionStatus.SUBMITTING: {
        ExecutionStatus.ACTIVE,
        ExecutionStatus.REJECTED,
        ExecutionStatus.ERROR,
    },
    ExecutionStatus.ACTIVE: {
        ExecutionStatus.PAUSED,
        ExecutionStatus.COMPLETING,
        ExecutionStatus.CANCELLING,
        ExecutionStatus.ERROR,
    },
    ExecutionStatus.PAUSED: {
        ExecutionStatus.RESUMING,
        ExecutionStatus.CANCELLING,
        ExecutionStatus.ERROR,
    },
    ExecutionStatus.RESUMING: {
        ExecutionStatus.ACTIVE,
        ExecutionStatus.ERROR,
    },
    ExecutionStatus.COMPLETING: {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.ERROR,
    },
    ExecutionStatus.COMPLETED: set(),  # Terminal
    ExecutionStatus.CANCELLING: {
        ExecutionStatus.CANCELLED,
        ExecutionStatus.ERROR,
    },
    ExecutionStatus.CANCELLED: set(),  # Terminal
    ExecutionStatus.REJECTED: set(),  # Terminal
    ExecutionStatus.ERROR: {
        ExecutionStatus.PENDING,  # Retry from start
        ExecutionStatus.CANCELLED,
    },
}


def is_valid_transition(from_status: ExecutionStatus, to_status: ExecutionStatus) -> bool:
    """Check if a state transition is valid.

    Args:
        from_status: Current execution status
        to_status: Target execution status

    Returns:
        True if the transition is allowed
    """
    allowed = VALID_TRANSITIONS.get(from_status, set())
    return to_status in allowed


def get_allowed_transitions(status: ExecutionStatus) -> set[ExecutionStatus]:
    """Get all allowed next states from the given status.

    Args:
        status: Current execution status

    Returns:
        Set of allowed next status values
    """
    return VALID_TRANSITIONS.get(status, set())
