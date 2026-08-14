"""ORDER_REJECTED (Commit 33 Part 1.4 #13).

Produced when the venue / broker explicitly rejects the order.  The event MUST
carry the ``reject_reason`` (e.g. ``VENUE_REJECTED`` / ``INVALID_ORDER`` /
``BROKER_UNAVAILABLE``) - a bare ``status = REJECTED`` without a reason is
never enough for audit and reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.order.domain.events.base import OrderEvent


@dataclass(frozen=True)
class OrderRejected(OrderEvent):
    """The order was rejected; the reason is always recorded."""

    reject_reason: Optional[str] = None

    event_type: str = "ORDER_REJECTED"
