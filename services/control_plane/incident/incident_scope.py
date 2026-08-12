"""
IncidentScope — how much of the system an incident affects.

An incident is not necessarily global: a Strategy-A position failure only
affects STRATEGY:A, while a global ledger integrity failure is GLOBAL
(spec section 7).
"""

from __future__ import annotations

from enum import Enum


_SCOPE_WIDTH = {
    "GLOBAL": 5,
    "SERVICE": 4,
    "ACCOUNT": 3,
    "STRATEGY": 2,
    "INSTRUMENT": 1,
    "VENUE": 1,
}


class IncidentScope(str, Enum):
    GLOBAL = "GLOBAL"
    """Affects the whole system."""

    SERVICE = "SERVICE"
    """Affects a single service."""

    ACCOUNT = "ACCOUNT"
    """Affects a single account."""

    STRATEGY = "STRATEGY"
    """Affects a single strategy."""

    INSTRUMENT = "INSTRUMENT"
    """Affects a single instrument."""

    VENUE = "VENUE"
    """Affects a single venue."""

    @property
    def width(self) -> int:
        """How much of the system this scope covers (wider = more damage)."""
        return _SCOPE_WIDTH[self.value]

    def can_expand_to(self, target: "IncidentScope") -> bool:
        """True if ``target`` covers a strictly wider blast radius than self.

        Used for scope aggregation: STRATEGY -> SERVICE -> GLOBAL is a valid
        escalation, GLOBAL -> STRATEGY is not (spec section 34).
        """
        if not isinstance(target, IncidentScope):
            raise TypeError(
                f"target must be IncidentScope, got {type(target).__name__}"
            )
        return target.width > self.width
