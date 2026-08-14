"""ORDER_ACCEPTED (Commit 33 Part 1.4 #12).

Produced when the execution gateway reports the venue accepted the order:

.. code-block:: text

    Execution Gateway (ACCEPTED)
        -> Order (ACCEPTED)
        -> ORDER_ACCEPTED

Payload: ``order_id`` / ``venue_order_id`` / ``execution_request_id``.  The
``venue_order_id`` is fixed at this moment and can never be edited afterwards -
a new fact means a new event, never a modified one (#24).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.order.domain.events.base import OrderEvent


@dataclass(frozen=True)
class OrderAccepted(OrderEvent):
    """The venue accepted the order."""

    venue_order_id: Optional[str] = None
    execution_request_id: Optional[str] = None

    event_type: str = "ORDER_ACCEPTED"
