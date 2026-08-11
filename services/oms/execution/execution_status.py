"""Execution status enum."""
from __future__ import annotations

from enum import Enum, auto


class ExecutionStatus(Enum):
    """Status of an execution request or report."""

    SUBMITTED = auto()
    ACCEPTED = auto()
    REJECTED = auto()
    PARTIALLY_FILLED = auto()
    FILLED = auto()
    CANCEL_PENDING = auto()
    CANCELLED = auto()
    EXPIRED = auto()
    UNKNOWN = auto()

    @property
    def label(self) -> str:
        _labels = {
            ExecutionStatus.SUBMITTED: "Submitted",
            ExecutionStatus.ACCEPTED: "Accepted",
            ExecutionStatus.REJECTED: "Rejected",
            ExecutionStatus.PARTIALLY_FILLED: "Partially Filled",
            ExecutionStatus.FILLED: "Filled",
            ExecutionStatus.CANCEL_PENDING: "Cancel Pending",
            ExecutionStatus.CANCELLED: "Cancelled",
            ExecutionStatus.EXPIRED: "Expired",
            ExecutionStatus.UNKNOWN: "Unknown",
        }
        return _labels[self]

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL

    @property
    def is_unknown(self) -> bool:
        return self == ExecutionStatus.UNKNOWN

    @property
    def is_fill(self) -> bool:
        return self in (ExecutionStatus.PARTIALLY_FILLED, ExecutionStatus.FILLED)

    @property
    def is_rejected(self) -> bool:
        return self in (ExecutionStatus.REJECTED,)


_TERMINAL = frozenset({
    ExecutionStatus.FILLED,
    ExecutionStatus.CANCELLED,
    ExecutionStatus.REJECTED,
    ExecutionStatus.EXPIRED,
})
