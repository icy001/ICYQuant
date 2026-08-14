"""Order aggregate (Commit 33 Part 1.1).

An :class:`Order` is the OMS's formal trading order - created only after an
order request reaches HANDOFF.  The distinction is fixed at this boundary:

.. code-block:: text

    Order Request  = "I ask the system to create an order"
    Order          = "the system has formally created the order"

The order is immutable except for ``status`` / ``updated_at``.  The full
authorization lineage (intent / authorization / certificate / decision /
strategy / session / signal / correlation) is fixed at creation and can never
be overwritten - that is what future reconciliation needs to answer *"why was
this order allowed to exist?"*.

Quantity and price are :class:`~decimal.Decimal`, never binary floating point,
so ``0.1 + 0.2`` can never quietly become ``0.30000000000000004`` in an order.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Optional

from services.order.domain.order_side import OrderSide
from services.order.domain.order_status import OrderStatus
from services.order.domain.order_type import OrderType
from services.order.domain.time_in_force import TimeInForce


@dataclass(frozen=True)
class Order:
    """Immutable OMS order aggregate."""

    order_id: str
    order_request_id: str

    intent_id: str
    authorization_id: str
    certificate_id: str
    decision_id: str

    strategy_id: str
    session_id: str
    signal_id: str
    correlation_id: str

    symbol: str
    side: OrderSide
    quantity: Decimal

    order_type: OrderType
    time_in_force: TimeInForce
    limit_price: Optional[Decimal]

    status: OrderStatus

    created_at: datetime
    updated_at: datetime
    client_order_id: Optional[str] = None
    reject_reason: Optional[str] = None
    venue_order_id: Optional[str] = None

    def with_status(
        self,
        status: OrderStatus,
        *,
        at: Optional[datetime] = None,
    ) -> "Order":
        """A new order with ``status`` and a refreshed ``updated_at``.

        Identity and lineage never change; only the status and the updated-at
        timestamp move (Commit 33 Part 1.1 #22).  ``reject_reason`` is kept
        unless the caller explicitly replaces it.
        """
        updated_at = at if at is not None else datetime.now()
        return replace(self, status=status, updated_at=updated_at)

    def with_reject(
        self,
        reason: str,
        *,
        at: Optional[datetime] = None,
    ) -> "Order":
        """A new REJECTED order carrying the rejection reason (Commit 33 #21).

        ``status = REJECTED`` alone is never enough - audit / reconciliation /
        trade-book need to know *why* the order failed.
        """
        updated_at = at if at is not None else datetime.now()
        return replace(
            self,
            status=OrderStatus.REJECTED,
            reject_reason=reason,
            updated_at=updated_at,
        )

    def with_venue_order_id(
        self,
        venue_order_id: str,
        *,
        at: Optional[datetime] = None,
    ) -> "Order":
        """A new order recording the venue/broker order id (Commit 33 #16).

        The identity hierarchy is fixed: ``order_id`` (OMS) ->
        ``client_order_id`` (broker-facing) -> ``venue_order_id`` (exchange).
        Status is left untouched - callers transition first, then attach the
        venue id.
        """
        updated_at = at if at is not None else datetime.now()
        return replace(
            self,
            venue_order_id=venue_order_id,
            updated_at=updated_at,
        )

    def as_dict(self) -> dict:
        """Plain mapping for persistence / adapters.

        Decimals and datetimes are serialized as strings so the mapping stays
        JSON-friendly; ``limit_price`` keeps ``None`` for MARKET orders.
        """
        return {
            "order_id": self.order_id,
            "order_request_id": self.order_request_id,
            "client_order_id": self.client_order_id,
            "intent_id": self.intent_id,
            "authorization_id": self.authorization_id,
            "certificate_id": self.certificate_id,
            "decision_id": self.decision_id,
            "strategy_id": self.strategy_id,
            "session_id": self.session_id,
            "signal_id": self.signal_id,
            "correlation_id": self.correlation_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": str(self.quantity),
            "order_type": self.order_type.value,
            "time_in_force": self.time_in_force.value,
            "limit_price": None if self.limit_price is None else str(self.limit_price),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "reject_reason": self.reject_reason,
            "venue_order_id": self.venue_order_id,
        }
