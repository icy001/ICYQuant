"""Order validator (Commit 33 Part 1.2).

The validator answers one question: *"is this order domain object valid?"* -
identity, quantity, order type, price, time-in-force, lineage and state.

It deliberately never answers *"may the strategy trade?"*: that is the risk
engine's job (Commit 31).  ``BUY 100 NVDA`` can be perfectly valid here while
being rejected by risk - the two concerns never mix.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from services.order.domain.order import Order
from services.order.domain.order_type import OrderType
from services.order.request.state import OrderRequestState

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from services.order.request.normalization import NormalizedOrderRequest
    from services.order.request.repository import OrderRequestSnapshot


class OrderValidationError(ValueError):
    """Raised when an order (or its originating request) is invalid."""


_LINEAGE_FIELDS = (
    "intent_id",
    "authorization_id",
    "certificate_id",
    "decision_id",
    "strategy_id",
    "session_id",
    "signal_id",
    "correlation_id",
)


class OrderValidator:
    """Structural validation for orders and handoff requests."""

    def validate_request(
        self,
        request: "OrderRequestSnapshot | NormalizedOrderRequest",
    ) -> None:
        """Validate an order request before it becomes an order."""
        if request is None:
            raise OrderValidationError("order request is required")

        if getattr(request, "state", None) != OrderRequestState.HANDOFF:
            raise OrderValidationError(
                "order can only be created from a HANDOFF order request"
            )

        for field in _LINEAGE_FIELDS:
            if not getattr(request, field, None):
                raise OrderValidationError(f"order request missing {field}")

        quantity = Decimal(str(request.quantity))
        if quantity <= 0:
            raise OrderValidationError("order quantity must be positive")

        order_type = OrderType(request.order_type.strip().upper())
        limit_price = (
            None if request.limit_price is None else Decimal(str(request.limit_price))
        )
        self._check_price(order_type, limit_price)

    def validate(self, order: Order) -> None:
        """Validate an order domain object before persisting or transitioning."""
        if order is None:
            raise OrderValidationError("order is required")

        if not order.order_id:
            raise OrderValidationError("order_id is required")
        if not order.order_request_id:
            raise OrderValidationError("order_request_id is required")

        for field in _LINEAGE_FIELDS:
            if not getattr(order, field):
                raise OrderValidationError(f"order missing {field}")

        if order.quantity <= 0:
            raise OrderValidationError("order quantity must be positive")

        self._check_price(order.order_type, order.limit_price)

    @staticmethod
    def _check_price(order_type: OrderType, limit_price) -> None:
        if order_type is OrderType.LIMIT:
            if limit_price is None or limit_price <= 0:
                raise OrderValidationError(
                    "LIMIT order requires a positive limit_price"
                )
        else:  # MARKET
            if limit_price is not None:
                raise OrderValidationError("MARKET order cannot have a limit_price")
