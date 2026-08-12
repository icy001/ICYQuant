"""
VenueControlDecision — the granular outcome of Venue Control
(Commit 26 Part 1.4, spec section 9).
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import VenueState


@dataclass(frozen=True)
class VenueControlDecision:

    venue: str

    state: VenueState

    allow_new_orders: bool

    allow_cancel_orders: bool

    allow_reduce_orders: bool

    allow_emergency_flatten: bool

    reason: str

    @property
    def allow_any_orders(self) -> bool:
        return (
            self.allow_new_orders
            or self.allow_cancel_orders
            or self.allow_reduce_orders
            or self.allow_emergency_flatten
        )
