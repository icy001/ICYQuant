"""Order Request domain event types.

Every state change of an ``OrderRequest`` aggregate produces exactly one
explicit domain event.  We deliberately avoid a generic
``ORDER_REQUEST_UPDATED`` event because downstream consumers (Ledger,
Position, Reconciliation, Audit, Monitoring) must know *what happened*:

- ``ORDER_REQUEST_SUBMITTED`` and ``ORDER_REQUEST_REJECTED`` are completely
  different business facts, even though both are "an update".

The event type describes *why* the aggregate changed; the aggregate
:class:`~services.order.request.state.OrderRequestState` describes *what it is
now*.
"""

from enum import Enum


class OrderRequestEventType(str, Enum):
    """Stable, explicit domain event types for the order request lifecycle.

    Values are stable string constants so they can be persisted, serialized
    onto an event bus, and compared without the enum instance itself.
    """

    ORDER_REQUEST_CREATED = "ORDER_REQUEST_CREATED"

    ORDER_REQUEST_VALIDATED = "ORDER_REQUEST_VALIDATED"

    ORDER_REQUEST_NORMALIZED = "ORDER_REQUEST_NORMALIZED"

    ORDER_REQUEST_SUBMITTED = "ORDER_REQUEST_SUBMITTED"

    ORDER_REQUEST_ACCEPTED = "ORDER_REQUEST_ACCEPTED"

    ORDER_REQUEST_REJECTED = "ORDER_REQUEST_REJECTED"

    ORDER_REQUEST_CANCELLED = "ORDER_REQUEST_CANCELLED"

    ORDER_REQUEST_EXPIRED = "ORDER_REQUEST_EXPIRED"

    ORDER_REQUEST_HANDOFF = "ORDER_REQUEST_HANDOFF"


__all__ = [
    "OrderRequestEventType",
]
