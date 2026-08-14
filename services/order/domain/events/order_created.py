"""ORDER_CREATED (Commit 33 Part 1.4 #10).

Produced when an order request reaches HANDOFF and the order is formally
created:

.. code-block:: text

    Order Request (HANDOFF) -> Order (CREATED) -> ORDER_CREATED
"""

from __future__ import annotations

from dataclasses import dataclass

from services.order.domain.events.base import OrderEvent


@dataclass(frozen=True)
class OrderCreated(OrderEvent):
    """The order was formally created from a HANDOFF order request."""

    event_type: str = "ORDER_CREATED"
