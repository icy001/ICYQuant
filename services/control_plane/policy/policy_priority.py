"""
PolicyPriority — escalation rank of a policy.

Multiple policies can fire in the same evaluation.  The engine must resolve
them deterministically, so every priority carries an explicit numeric rank:

    LOW < MEDIUM < HIGH < CRITICAL

Example mapping used by the health policies:

    Market Data stale          → MEDIUM
    Risk Engine degraded       → HIGH
    Risk Engine dead           → CRITICAL
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, List


class PolicyPriority(str, Enum):
    """Escalation priority of a policy / rule."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        """Numeric rank used for comparisons (LOW=0 … CRITICAL=3)."""
        return _RANK[self]


_RANK = {
    PolicyPriority.LOW: 0,
    PolicyPriority.MEDIUM: 1,
    PolicyPriority.HIGH: 2,
    PolicyPriority.CRITICAL: 3,
}


def priority_ge(a: PolicyPriority, b: PolicyPriority) -> bool:
    """True when ``a`` is at least as severe as ``b``."""
    return a.rank >= b.rank


def highest_priority(priorities: Iterable[PolicyPriority]) -> PolicyPriority:
    """Most severe priority from an iterable (empty → LOW)."""
    values = list(priorities)
    if not values:
        return PolicyPriority.LOW
    return max(values, key=lambda p: p.rank)


def lowest_priority(priorities: Iterable[PolicyPriority]) -> PolicyPriority:
    """Least severe priority from an iterable (empty → LOW)."""
    values = list(priorities)
    if not values:
        return PolicyPriority.LOW
    return min(values, key=lambda p: p.rank)


def sorted_priorities(priorities: Iterable[PolicyPriority]) -> List[PolicyPriority]:
    """Priorities ordered most-severe first."""
    return sorted(priorities, key=lambda p: p.rank, reverse=True)
