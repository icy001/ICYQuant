"""
Recovery state machine.

The recovery lifecycle follows a strict pipeline:

    DETECTED -> ISOLATING -> ISOLATED -> RECOVERING -> RECONCILING
        -> VERIFYING -> RAMPING_UP -> COMPLETED

Any stage may fail:

    any -> FAILED -> (RETRY -> back to the failed stage | ESCALATED)

Recovery must never jump stages, and it must never complete without passing
through VERIFYING -> RAMPING_UP.  This module also classifies step failures so
the orchestrator can decide between automatic retry and escalation.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional, Set


class RecoveryState(str, Enum):
    """Lifecycle state of a single recovery session."""

    DETECTED = "DETECTED"
    """Incident detected, recovery plan is being prepared."""

    ISOLATING = "ISOLATING"
    """Trading is being restricted / halted so state can stabilise."""

    ISOLATED = "ISOLATED"
    """Trading isolated, recovery baseline is frozen."""

    RECOVERING = "RECOVERING"
    """Rebuild / replay steps are running."""

    RECONCILING = "RECONCILING"
    """Ledger vs position vs event reconciliation."""

    VERIFYING = "VERIFYING"
    """Multi-layer integrity verification."""

    RAMPING_UP = "RAMPING_UP"
    """Verified, trading is being ramped back up gradually."""

    COMPLETED = "COMPLETED"
    """Recovery finished, trading may resume via policy evaluation."""

    FAILED = "FAILED"
    """A step failed; the recovery may retry or escalate."""

    ESCALATED = "ESCALATED"
    """Recovery failed and was escalated for human intervention."""

    @property
    def is_terminal(self) -> bool:
        return self in (RecoveryState.COMPLETED, RecoveryState.ESCALATED)

    @property
    def is_active(self) -> bool:
        """States that still require the recovery session to keep running."""
        return not self.is_terminal and self is not RecoveryState.FAILED


class RecoveryStateMachine:
    """Allowed recovery state transitions."""

    ALLOWED_TRANSITIONS: Dict[RecoveryState, Set[RecoveryState]] = {
        RecoveryState.DETECTED: {
            RecoveryState.ISOLATING,
            RecoveryState.FAILED,
            RecoveryState.ESCALATED,
        },
        RecoveryState.ISOLATING: {
            RecoveryState.ISOLATED,
            RecoveryState.FAILED,
            RecoveryState.ESCALATED,
        },
        RecoveryState.ISOLATED: {
            RecoveryState.RECOVERING,
            RecoveryState.FAILED,
            RecoveryState.ESCALATED,
        },
        RecoveryState.RECOVERING: {
            RecoveryState.RECONCILING,
            RecoveryState.FAILED,
            RecoveryState.ESCALATED,
        },
        RecoveryState.RECONCILING: {
            RecoveryState.VERIFYING,
            RecoveryState.FAILED,
            RecoveryState.ESCALATED,
        },
        RecoveryState.VERIFYING: {
            RecoveryState.RAMPING_UP,
            RecoveryState.FAILED,
            RecoveryState.ESCALATED,
        },
        RecoveryState.RAMPING_UP: {
            RecoveryState.COMPLETED,
            RecoveryState.FAILED,
            RecoveryState.ESCALATED,
        },
        # terminal states
        RecoveryState.COMPLETED: set(),
        RecoveryState.ESCALATED: set(),
        # a failed recovery may retry (resume from a checkpoint) or escalate
        RecoveryState.FAILED: {
            RecoveryState.ISOLATING,
            RecoveryState.RECOVERING,
            RecoveryState.RECONCILING,
            RecoveryState.VERIFYING,
            RecoveryState.RAMPING_UP,
            RecoveryState.ESCALATED,
        },
    }

    #: Canonical ordering used for progress reporting.
    SEQUENCE: tuple = (
        RecoveryState.DETECTED,
        RecoveryState.ISOLATING,
        RecoveryState.ISOLATED,
        RecoveryState.RECOVERING,
        RecoveryState.RECONCILING,
        RecoveryState.VERIFYING,
        RecoveryState.RAMPING_UP,
        RecoveryState.COMPLETED,
    )

    @classmethod
    def can_transition(cls, from_state: RecoveryState, to_state: RecoveryState) -> bool:
        return to_state in cls.ALLOWED_TRANSITIONS.get(from_state, set())

    @classmethod
    def assert_transition(cls, from_state: RecoveryState, to_state: RecoveryState) -> None:
        if not cls.can_transition(from_state, to_state):
            raise RecoveryStateTransitionError(from_state, to_state)


class RecoveryStateTransitionError(Exception):
    """Raised when a recovery state transition is rejected."""

    def __init__(self, from_state: RecoveryState, to_state: RecoveryState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid recovery state transition: {from_state.value} -> {to_state.value}"
        )


class FailureClass(str, Enum):
    """Classification of a step failure — drives retry vs escalate."""

    TRANSIENT = "TRANSIENT"
    """Temporary infrastructure failure (timeout / connection). Auto-retry."""

    RECOVERABLE = "RECOVERABLE"
    """Recoverable with a bounded number of retries."""

    INTEGRITY = "INTEGRITY"
    """State integrity problem (event gap / checksum). No auto retry."""

    FATAL = "FATAL"
    """Unrecoverable without human intervention."""


#: error-code / text markers that classify a failure message.
_TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "connection",
    "network",
    "busy",
    "temporary",
    "unavailable",
    "transient",
)
_RECOVERABLE_MARKERS = (
    "retry",
    "stale",
    "conflict",
    "resource",
    "recoverable",
)
_INTEGRITY_MARKERS = (
    "gap",
    "checksum",
    "mismatch",
    "integrity",
    "sequence",
    "divergence",
    "corrupt",
)
_FATAL_MARKERS = (
    "fatal",
    "denied",
    "rejected",
    "unauthorized",
    "invalid",
)


def classify_failure(error: Optional[str] = "", error_code: str = "") -> FailureClass:
    """Classify a step failure.

    Explicit error codes win; otherwise the error text is matched against a
    set of markers.  Unknown failures default to :data:`FailureClass.RECOVERABLE`.
    """
    code = (error_code or "").upper()
    if code:
        if any(marker.upper() in code for marker in _INTEGRITY_MARKERS):
            return FailureClass.INTEGRITY
        if any(marker.upper() in code for marker in _FATAL_MARKERS):
            return FailureClass.FATAL
        if any(marker.upper() in code for marker in _TRANSIENT_MARKERS):
            return FailureClass.TRANSIENT
        if any(marker.upper() in code for marker in _RECOVERABLE_MARKERS):
            return FailureClass.RECOVERABLE

    text = (error or "").lower()
    if any(marker in text for marker in _INTEGRITY_MARKERS):
        return FailureClass.INTEGRITY
    if any(marker in text for marker in _FATAL_MARKERS):
        return FailureClass.FATAL
    if any(marker in text for marker in _TRANSIENT_MARKERS):
        return FailureClass.TRANSIENT
    if any(marker in text for marker in _RECOVERABLE_MARKERS):
        return FailureClass.RECOVERABLE
    return FailureClass.RECOVERABLE


__all__ = [
    "RecoveryState",
    "RecoveryStateMachine",
    "RecoveryStateTransitionError",
    "FailureClass",
    "classify_failure",
]
