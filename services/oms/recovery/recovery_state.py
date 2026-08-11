"""RecoveryState enum."""
from __future__ import annotations

from enum import Enum, auto


class RecoveryState(Enum):
    """State of a recovery job."""

    PENDING = auto()
    RUNNING = auto()
    WAITING = auto()
    RECOVERED = auto()
    RECONCILIATION_REQUIRED = auto()
    FAILED = auto()
    ESCALATED = auto()

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def is_terminal(self) -> bool:
        return self in (
            RecoveryState.RECOVERED,
            RecoveryState.FAILED,
            RecoveryState.ESCALATED,
        )

    @property
    def is_success(self) -> bool:
        return self == RecoveryState.RECOVERED
