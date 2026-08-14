"""Command state transition engine (Commit 29 Part 1.3 §5-6).

The durable command lifecycle is the single source of truth for where a
control command currently stands. Every state change passes through
``StateTransitionEngine.transition`` so illegal jumps (e.g.
RECEIVED -> SUCCEEDED, EXECUTING -> AUTHORIZED, REJECTED -> EXECUTING)
are rejected before they can ever be persisted (§4-6).

State machine (Part 1.3 §3, extended with the recovery states of §16/§24-26)::

    RECEIVED -> AUTHORIZING -> {REJECTED, WAITING_APPROVAL, AUTHORIZED, FAILED}
    AUTHORIZED -> DISPATCHING -> EXECUTING -> {SUCCEEDED, FAILED, UNKNOWN,
                                                RECOVERY_REQUIRED}
    UNKNOWN -> {RECOVERY_REQUIRED, MANUAL_INTERVENTION}
    RECOVERY_REQUIRED -> {EXECUTING, SUCCEEDED, AUTHORIZED, MANUAL_INTERVENTION}
    WAITING_APPROVAL -> {AUTHORIZED, REJECTED, CANCELLED}
    FAILED -> {AUTHORIZED, CANCELLED}
    SUCCEEDED / REJECTED / CANCELLED / MANUAL_INTERVENTION are terminal.
"""

from __future__ import annotations

from .errors import ControlPlaneError


class InvalidTransition(ControlPlaneError):
    """A command attempted an illegal lifecycle transition (§5)."""


ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "RECEIVED": frozenset({"AUTHORIZING", "CANCELLED"}),
    "AUTHORIZING": frozenset(
        {"AUTHORIZED", "WAITING_APPROVAL", "REJECTED", "FAILED"}
    ),
    "WAITING_APPROVAL": frozenset({"AUTHORIZED", "REJECTED", "CANCELLED"}),
    "AUTHORIZED": frozenset({"DISPATCHING", "CANCELLED"}),
    "DISPATCHING": frozenset({"EXECUTING", "FAILED"}),
    "EXECUTING": frozenset(
        {"SUCCEEDED", "FAILED", "UNKNOWN", "RECOVERY_REQUIRED"}
    ),
    "FAILED": frozenset({"AUTHORIZED", "CANCELLED"}),
    "UNKNOWN": frozenset({"RECOVERY_REQUIRED", "MANUAL_INTERVENTION"}),
    "RECOVERY_REQUIRED": frozenset(
        {"EXECUTING", "SUCCEEDED", "AUTHORIZED", "MANUAL_INTERVENTION"}
    ),
    "SUCCEEDED": frozenset(),
    "REJECTED": frozenset(),
    "CANCELLED": frozenset(),
    "MANUAL_INTERVENTION": frozenset(),
}


class StateTransitionEngine:
    """The single, validated gateway for command state changes (§6).

    Returns the target state on success and raises ``InvalidTransition``
    otherwise, so callers can never persist an unvalidated jump.
    """

    def transition(self, current: str, target: str) -> str:
        allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
        if target not in allowed:
            raise InvalidTransition(f"{current} -> {target}")
        return target
