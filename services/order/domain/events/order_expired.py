"""ORDER_EXPIRED (Commit 33 Part 1.4 #16).

Produced when a Time-In-Force rule makes the order lapse naturally (e.g. a DAY
order that was never filled).
"""

from __future__ import annotations

from dataclasses import dataclass

from services.order.domain.events.base import OrderEvent


@dataclass(frozen=True)
class OrderExpired(OrderEvent):
    """The order expired by its Time-In-Force."""

    event_type: str = "ORDER_EXPIRED"
