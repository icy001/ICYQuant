"""Order event base model (Commit 33 Part 1.4).

An :class:`OrderEvent` answers *why* an order state changed, while
:class:`~services.order.domain.order_status.OrderStatus` only answers *what* the
order currently is:

.. code-block:: text

    Order.status = ACCEPTED       -> "what the order is now"
    OrderAccepted (event)         -> "when / who / from which request"

Every event carries:

* its own immutable identity (``event_id``, e.g. ``EVT-ORD-000001``) - never to
  be confused with the order id (#4)
* the aggregate identity (``aggregate_type = "ORDER"`` / ``aggregate_id`` = the
  order id) (#5)
* the trace chain: ``correlation_id`` for the whole business flow (#6),
  ``causation_id`` for *what caused this event* - e.g. the command that
  triggered it or the previous event (#7)
* a per-aggregate monotonic ``sequence`` (1, 2, 3, ...) so reconciliation can
  spot gaps - sequence 4 may never appear before sequence 2 (#8 / #23)
* ``payload_version`` so old events stay readable when the schema evolves (#9)

Events are immutable facts: when something new happens, a NEW event is produced
- the old event is never modified (#24).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class OrderEvent:
    """Immutable base for every order domain event.

    Fields are all-defaulted so subclasses can override ``event_type`` with a
    per-class default; :meth:`__post_init__` enforces the real invariants
    (fail-closed), so an incomplete event can never exist.
    """

    event_id: str = ""
    event_type: str = "ORDER_EVENT"
    aggregate_id: str = ""
    aggregate_type: str = "ORDER"
    order_id: str = ""
    order_request_id: str = ""
    correlation_id: str = ""
    causation_id: Optional[str] = None
    occurred_at: Optional[datetime] = None
    sequence: int = 0
    payload_version: int = 1

    def __post_init__(self) -> None:
        expected_type = type(self).__dataclass_fields__["event_type"].default
        if self.event_type != expected_type:
            raise ValueError(
                f"event_type must be {expected_type!r} for {type(self).__name__}"
            )
        if not self.event_id:
            raise ValueError("event_id is required")
        if not self.aggregate_type:
            raise ValueError("aggregate_type is required")
        if not self.aggregate_id:
            raise ValueError("aggregate_id is required")
        if not self.order_id:
            raise ValueError("order_id is required")
        if not self.order_request_id:
            raise ValueError("order_request_id is required")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")
        if self.occurred_at is None:
            raise ValueError("occurred_at is required")
        if self.sequence < 1:
            raise ValueError("sequence must be a positive integer")
