from __future__ import annotations

from .enums import OrderStatus
from .events import OrderTransition

# EXPIRE and REPLACE transitions reserved for future execution scenarios


TRANSITIONS = {
    (OrderStatus.NEW, OrderTransition.SUBMIT): OrderStatus.PENDING,
    (OrderStatus.NEW, OrderTransition.ACCEPT): OrderStatus.PENDING,
    (OrderStatus.NEW, OrderTransition.CANCEL): OrderStatus.CANCELLED,
    (OrderStatus.NEW, OrderTransition.REJECT): OrderStatus.REJECTED,
    (OrderStatus.PENDING, OrderTransition.PARTIAL_FILL): OrderStatus.PARTIALLY_FILLED,
    (OrderStatus.PENDING, OrderTransition.FILL): OrderStatus.FILLED,
    (OrderStatus.PENDING, OrderTransition.CANCEL): OrderStatus.CANCELLED,
    (OrderStatus.PENDING, OrderTransition.REJECT): OrderStatus.REJECTED,
    (OrderStatus.PARTIALLY_FILLED, OrderTransition.PARTIAL_FILL): OrderStatus.PARTIALLY_FILLED,
    (OrderStatus.PARTIALLY_FILLED, OrderTransition.FILL): OrderStatus.FILLED,
    (OrderStatus.PARTIALLY_FILLED, OrderTransition.CANCEL): OrderStatus.CANCELLED,
}