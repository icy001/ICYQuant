"""ReconciliationStatus enum."""
from __future__ import annotations

from enum import Enum, auto


class ReconciliationStatus(Enum):
    """Status of a reconciliation attempt."""

    CONSISTENT = auto()
    OMS_STALE = auto()
    EXECUTION_STALE = auto()
    QUANTITY_MISMATCH = auto()
    PRICE_MISMATCH = auto()
    STATE_MISMATCH = auto()
    MISSING_EXECUTION = auto()
    DUPLICATE_EXECUTION = auto()
    UNKNOWN = auto()
    CRITICAL = auto()

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def is_consistent(self) -> bool:
        return self == ReconciliationStatus.CONSISTENT

    @property
    def is_critical(self) -> bool:
        return self == ReconciliationStatus.CRITICAL

    @property
    def needs_recovery(self) -> bool:
        return self in (
            ReconciliationStatus.OMS_STALE,
            ReconciliationStatus.MISSING_EXECUTION,
        )

    @property
    def needs_escalation(self) -> bool:
        return self in (
            ReconciliationStatus.CRITICAL,
            ReconciliationStatus.STATE_MISMATCH,
            ReconciliationStatus.QUANTITY_MISMATCH,
        )
