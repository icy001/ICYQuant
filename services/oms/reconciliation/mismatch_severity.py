"""MismatchSeverity enum."""
from __future__ import annotations

from enum import Enum, auto


class MismatchSeverity(Enum):
    """Severity of a reconciliation mismatch."""

    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()

    @property
    def label(self) -> str:
        return self.name.title()

    @property
    def is_critical(self) -> bool:
        return self == MismatchSeverity.CRITICAL

    @property
    def is_error(self) -> bool:
        return self in (MismatchSeverity.ERROR, MismatchSeverity.CRITICAL)
