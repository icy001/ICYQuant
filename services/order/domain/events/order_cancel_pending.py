"""ORDER_CANCEL_PENDING (Commit 33 Part 1.4 #14).

Produced when a cancel request has been SENT - not yet confirmed:

.. code-block:: text

    ACCEPTED -> CANCEL_PENDING -> ORDER_CANCEL_PENDING

It says "a cancellation was requested", never "the order is cancelled" - the
venue confirmation is a separate, later fact (ORDER_CANCELLED).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.order.domain.events.base import OrderEvent


@dataclass(frozen=True)
class OrderCancelPending(OrderEvent):
    """A cancel request was sent; the venue confirmation is pending."""

    execution_request_id: Optional[str] = None

    event_type: str = "ORDER_CANCEL_PENDING"
