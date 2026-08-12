"""
IncidentSeverity — how serious an incident is, with an explicit rank.

Rank order:
    INFO < LOW < MEDIUM < HIGH < CRITICAL < FATAL

Severity may be escalated without verification, but never downgraded directly:
downgrades must pass through mitigation + verification (spec section 19).
"""

from __future__ import annotations

from enum import Enum
from typing import Union


_SEVERITY_RANK = {
    "INFO": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
    "FATAL": 5,
}


class IncidentSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"

    @property
    def rank(self) -> int:
        """Higher rank means more severe."""
        return _SEVERITY_RANK[self.value]

    def can_escalate_to(self, target: "IncidentSeverity") -> bool:
        """True if target is strictly more severe than self."""
        if not isinstance(target, IncidentSeverity):
            raise TypeError(
                f"target must be IncidentSeverity, got {type(target).__name__}"
            )
        return target.rank > self.rank

    def can_degrade_to(self, target: "IncidentSeverity") -> bool:
        """True if target is strictly less severe than self.

        The model exposes the capability; the caller is responsible for
        enforcing that a downgrade is only allowed after mitigation and
        verification.
        """
        if not isinstance(target, IncidentSeverity):
            raise TypeError(
                f"target must be IncidentSeverity, got {type(target).__name__}"
            )
        return target.rank < self.rank

    # -- comparison -------------------------------------------------------

    def __lt__(self, other: Union["IncidentSeverity", str]) -> bool:
        if isinstance(other, str):
            other = IncidentSeverity(other)
        return self.rank < other.rank

    def __le__(self, other: Union["IncidentSeverity", str]) -> bool:
        if isinstance(other, str):
            other = IncidentSeverity(other)
        return self.rank <= other.rank

    def __gt__(self, other: Union["IncidentSeverity", str]) -> bool:
        if isinstance(other, str):
            other = IncidentSeverity(other)
        return self.rank > other.rank

    def __ge__(self, other: Union["IncidentSeverity", str]) -> bool:
        if isinstance(other, str):
            other = IncidentSeverity(other)
        return self.rank >= other.rank
