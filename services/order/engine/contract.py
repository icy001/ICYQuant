"""Order engine contracts (Commit 33 Part 1.1).

The create-order command carries no trading parameters: symbol / side /
quantity / order type / time in force / limit price all come from the
:class:`~services.order.request.normalization.NormalizedOrderRequest`.  There
is a single source of truth for every trade, so a request ``BUY 100`` can
never be turned into an order ``SELL 1000`` by a divergent command.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CreateOrderCommand:
    """Minimal command to create an order from a handoff order request.

    ``order_request_id`` ties the order to its request; ``client_order_id``
    reserves the OMS/broker/exchange correlation slot; ``timestamp`` is the
    authoritative order creation time (used as ``updated_at``).

    The actual order parameters are resolved from the order request - never
    from this command.
    """

    order_request_id: str
    client_order_id: str
    timestamp: datetime
