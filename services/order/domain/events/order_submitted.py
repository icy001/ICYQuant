"""ORDER_SUBMITTED (Commit 33 Part 1.4 #11).

Produced when the order enters the execution channel:

.. code-block:: text

    CREATED -> PENDING_SUBMIT -> SUBMITTED -> ORDER_SUBMITTED

Core payload: ``order_id`` / ``client_order_id`` / ``execution_request_id``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.order.domain.events.base import OrderEvent


@dataclass(frozen=True)
class OrderSubmitted(OrderEvent):
    """The order entered the execution channel (SUBMITTED)."""

    client_order_id: Optional[str] = None
    execution_request_id: Optional[str] = None

    event_type: str = "ORDER_SUBMITTED"
