"""AdmissionState — state machine for the order admission lifecycle.

Every order intent passes through this state machine before being admitted to OMS.
"""

from __future__ import annotations

from enum import Enum, auto


class AdmissionState(Enum):
    """State machine for order admission.

    RECEIVED → VALIDATING → VALIDATED → AUTHORIZING → AUTHORIZED →
    NORMALIZING → NORMALIZED → RESERVING → RESERVED → ADMITTED

    Terminal error states: REJECTED, BLOCKED, DUPLICATE, EXPIRED, RESERVATION_FAILED
    """

    RECEIVED = auto()
    VALIDATING = auto()
    VALIDATED = auto()
    AUTHORIZING = auto()
    AUTHORIZED = auto()
    NORMALIZING = auto()
    NORMALIZED = auto()
    RESERVING = auto()
    RESERVED = auto()
    ADMITTED = auto()

    # Terminal error states
    REJECTED = auto()
    BLOCKED = auto()
    DUPLICATE = auto()
    EXPIRED = auto()
    RESERVATION_FAILED = auto()

    @property
    def label(self) -> str:
        _labels = {
            AdmissionState.RECEIVED: "RECEIVED",
            AdmissionState.VALIDATING: "VALIDATING",
            AdmissionState.VALIDATED: "VALIDATED",
            AdmissionState.AUTHORIZING: "AUTHORIZING",
            AdmissionState.AUTHORIZED: "AUTHORIZED",
            AdmissionState.NORMALIZING: "NORMALIZING",
            AdmissionState.NORMALIZED: "NORMALIZED",
            AdmissionState.RESERVING: "RESERVING",
            AdmissionState.RESERVED: "RESERVED",
            AdmissionState.ADMITTED: "ADMITTED",
            AdmissionState.REJECTED: "REJECTED",
            AdmissionState.BLOCKED: "BLOCKED",
            AdmissionState.DUPLICATE: "DUPLICATE",
            AdmissionState.EXPIRED: "EXPIRED",
            AdmissionState.RESERVATION_FAILED: "RESERVATION_FAILED",
        }
        return _labels.get(self, "UNKNOWN")

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state (no further transitions)."""
        return self in (
            AdmissionState.ADMITTED,
            AdmissionState.REJECTED,
            AdmissionState.BLOCKED,
            AdmissionState.DUPLICATE,
            AdmissionState.EXPIRED,
            AdmissionState.RESERVATION_FAILED,
        )

    @property
    def is_success(self) -> bool:
        """Check if this state represents successful completion."""
        return self == AdmissionState.ADMITTED

    @property
    def is_error(self) -> bool:
        """Check if this state represents an error condition."""
        return self.is_terminal and not self.is_success

    @property
    def is_active(self) -> bool:
        """Check if admission is still in progress."""
        return not self.is_terminal


# ── State transition table ────────────────────────────────────

_VALID_TRANSITIONS = {
    AdmissionState.RECEIVED: {AdmissionState.VALIDATING, AdmissionState.REJECTED,
                              AdmissionState.DUPLICATE, AdmissionState.EXPIRED},
    AdmissionState.VALIDATING: {AdmissionState.VALIDATED, AdmissionState.REJECTED},
    AdmissionState.VALIDATED: {AdmissionState.AUTHORIZING, AdmissionState.BLOCKED},
    AdmissionState.AUTHORIZING: {AdmissionState.AUTHORIZED, AdmissionState.REJECTED,
                                 AdmissionState.BLOCKED},
    AdmissionState.AUTHORIZED: {AdmissionState.NORMALIZING, AdmissionState.BLOCKED},
    AdmissionState.NORMALIZING: {AdmissionState.NORMALIZED, AdmissionState.REJECTED},
    AdmissionState.NORMALIZED: {AdmissionState.RESERVING, AdmissionState.ADMITTED},
    AdmissionState.RESERVING: {AdmissionState.RESERVED, AdmissionState.RESERVATION_FAILED},
    AdmissionState.RESERVED: {AdmissionState.ADMITTED},
}


def can_transition(current: AdmissionState, target: AdmissionState) -> bool:
    """Check if a state transition is valid."""
    allowed = _VALID_TRANSITIONS.get(current, set())
    return target in allowed


def valid_transitions_from(state: AdmissionState) -> set:
    """Return all valid next states from the given state."""
    return _VALID_TRANSITIONS.get(state, set())
