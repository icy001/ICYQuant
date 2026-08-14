"""Control command lifecycle state (Commit 29 Part 1.1 §13-15).

The Control Plane has its own command lifecycle::

    RECEIVED
       ↓
    AUTHORIZING
       ↓
    AUTHORIZED
       ↓
    DISPATCHING
       ↓
    EXECUTING
       ↓
    SUCCEEDED

With the exception paths AUTHORIZING -> REJECTED and EXECUTING -> FAILED.
Arbitrary jumps (e.g. RECEIVED -> SUCCEEDED) are not permitted so we can
always tell exactly which step a command failed at (§15).
"""

from __future__ import annotations

from enum import Enum

from .errors import InvalidControlState


class ControlState(str, Enum):
    RECEIVED = "RECEIVED"
    AUTHORIZING = "AUTHORIZING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    AUTHORIZED = "AUTHORIZED"
    DISPATCHING = "DISPATCHING"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


CONTROL_STATE_TRANSITIONS: dict[ControlState, frozenset[ControlState]] = {
    ControlState.RECEIVED: frozenset(
        {ControlState.AUTHORIZING, ControlState.CANCELLED}
    ),
    ControlState.AUTHORIZING: frozenset(
        {
            ControlState.AUTHORIZED,
            ControlState.WAITING_APPROVAL,
            ControlState.REJECTED,
        }
    ),
    ControlState.WAITING_APPROVAL: frozenset(
        {ControlState.AUTHORIZED, ControlState.CANCELLED, ControlState.REJECTED}
    ),
    ControlState.AUTHORIZED: frozenset({ControlState.DISPATCHING}),
    ControlState.DISPATCHING: frozenset({ControlState.EXECUTING}),
    ControlState.EXECUTING: frozenset(
        {ControlState.SUCCEEDED, ControlState.FAILED}
    ),
    ControlState.SUCCEEDED: frozenset(),
    ControlState.FAILED: frozenset(),
    ControlState.REJECTED: frozenset(),
    ControlState.CANCELLED: frozenset(),
}


def is_valid_transition(current: ControlState, next_state: ControlState) -> bool:
    """Return whether ``current -> next_state`` is a legal lifecycle step (§15)."""
    return next_state in CONTROL_STATE_TRANSITIONS[current]


def validate_transition(current: ControlState, next_state: ControlState) -> None:
    """Raise ``InvalidControlState`` unless the transition is legal (§15)."""
    if not is_valid_transition(current, next_state):
        raise InvalidControlState(
            f"invalid control state transition: "
            f"{current.value} -> {next_state.value}"
        )
