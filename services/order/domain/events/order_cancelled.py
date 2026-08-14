"""ORDER_CANCELLED (Commit 33 Part 1.4 #15).

Produced ONLY after the execution / venue confirms the cancellation - never
proactively.  The engine waits for the real confirmation before emitting this
fact (#22).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.order.domain.events.base import OrderEvent


@dataclass(frozen=True)
class OrderCancelled(OrderEvent):
    """The venue confirmed the order was cancelled."""

    execution_request_id: Optional[str] = None

    event_type: str = "ORDER_CANCELLED"
