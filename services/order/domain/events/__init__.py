"""Order domain events (Commit 33 Part 1.4).

Events are immutable facts about an order's lifecycle - they answer *why* a
state changed, never *what* the state currently is (that is
:class:`~services.order.domain.order_status.OrderStatus`).  Concrete events
only add their payload fields and default ``event_type``.
"""

from services.order.domain.events.base import OrderEvent
from services.order.domain.events.order_accepted import OrderAccepted
from services.order.domain.events.order_cancel_pending import OrderCancelPending
from services.order.domain.events.order_cancelled import OrderCancelled
from services.order.domain.events.order_created import OrderCreated
from services.order.domain.events.order_expired import OrderExpired
from services.order.domain.events.order_rejected import OrderRejected
from services.order.domain.events.order_submitted import OrderSubmitted

__all__ = [
    "OrderAccepted",
    "OrderCancelPending",
    "OrderCancelled",
    "OrderCreated",
    "OrderEvent",
    "OrderExpired",
    "OrderRejected",
    "OrderSubmitted",
]
