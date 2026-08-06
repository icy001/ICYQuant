"""Order Simulator — order validation, state management, and lifecycle tracking.

Supports Market, Limit, Stop, and Stop-Limit orders with partial fills
and remaining order book simulation.

Order Lifecycle::

    Created → Validated → Submitted → Partially Filled → Filled
                                    → Rejected
                                    → Cancelled
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class OrderType(str, Enum):
    """Supported order types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    """Order lifecycle status."""

    CREATED = "created"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class FillStatus(str, Enum):
    """Trade fill status."""

    FILLED = "filled"
    PARTIAL = "partial"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class Order:
    """An executable trading order."""

    order_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    side: str = "buy"  # buy, sell
    order_type: OrderType = OrderType.MARKET
    quantity: float = 0.0
    price: Optional[float] = None  # required for limit/stop orders
    stop_price: Optional[float] = None  # required for stop orders
    status: OrderStatus = OrderStatus.CREATED
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strategy_id: Optional[str] = None
    backtest_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class OrderSimulator:
    """Order validation, simulation, and lifecycle management.

    Simulates realistic order handling including:
    * Order type validation (Market/Limit/Stop/Stop-Limit)
    * Price and quantity bounds checking
    * Partial fill tracking
    * Order cancellation and expiration
    """

    def __init__(self) -> None:
        self._active_orders: Dict[str, Order] = {}
        self._order_history: List[Order] = []
        self._min_order_value: float = 0.0
        self._max_order_quantity: float = float("inf")

    # ── order creation ─────────────────────────────────────────────────────

    def create_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Order:
        """Create a new order.

        Args:
            symbol: Ticker symbol.
            side: buy or sell.
            quantity: Order quantity.
            order_type: MARKET, LIMIT, STOP, or STOP_LIMIT.
            price: Required for LIMIT orders.
            stop_price: Required for STOP orders.
            metadata: Optional metadata.

        Returns:
            The created Order object.
        """
        order = Order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            metadata=metadata or {},
        )
        return order

    # ── validation ─────────────────────────────────────────────────────────

    def validate(self, order_data: Dict[str, Any]) -> bool:
        """Validate an order.

        Returns False if the order should be rejected.
        """
        order_type = order_data.get("order_type", "market")
        quantity = order_data.get("quantity", order_data.get("strength", 0))
        price = order_data.get("price")

        # Quantity check
        if not quantity or quantity <= 0:
            logger.warning("Order rejected: invalid quantity %s", quantity)
            return False

        # Order type specific checks
        if order_type in (OrderType.LIMIT.value, OrderType.STOP_LIMIT.value):
            if not price or price <= 0:
                logger.warning("Order rejected: limit order without valid price")
                return False

        if order_type in (OrderType.STOP.value, OrderType.STOP_LIMIT.value):
            if not order_data.get("stop_price"):
                logger.warning("Order rejected: stop order without stop price")
                return False

        # Size checks
        if quantity > self._max_order_quantity:
            logger.warning("Order rejected: quantity %s exceeds max %s", quantity, self._max_order_quantity)
            return False

        return True

    def validate_order(self, order: Order) -> bool:
        """Validate an Order object."""
        return self.validate(order.__dict__)

    # ── lifecycle ──────────────────────────────────────────────────────────

    def submit(self, order: Order) -> Order:
        """Submit an order (mark as validated and ready for execution)."""
        if order.status != OrderStatus.CREATED:
            logger.warning("Cannot submit order in state: %s", order.status.value)
            return order

        order.status = OrderStatus.VALIDATED
        order.updated_at = datetime.now(timezone.utc)

        if not self.validate_order(order):
            order.status = OrderStatus.REJECTED
            order.updated_at = datetime.now(timezone.utc)
            return order

        order.status = OrderStatus.SUBMITTED
        self._active_orders[order.order_id] = order
        logger.info("Order submitted: %s %s %s x%.0f", order.symbol, order.side, order.order_type.value, order.quantity)
        return order

    def update_fill(
        self,
        order: Order,
        filled_qty: float,
        fill_price: float,
    ) -> Order:
        """Update order with partial or complete fill."""
        order.filled_quantity += filled_qty

        # Update average fill price
        if order.filled_quantity > 0:
            order.avg_fill_price = (
                (order.avg_fill_price * (order.filled_quantity - filled_qty) + fill_price * filled_qty)
                / order.filled_quantity
            )

        # Update status
        if order.filled_quantity >= order.quantity - 1e-8:
            order.status = OrderStatus.FILLED
            self._active_orders.pop(order.order_id, None)
            self._order_history.append(order)
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

        order.updated_at = datetime.now(timezone.utc)
        return order

    def cancel(self, order: Order) -> Order:
        """Cancel an active order."""
        if order.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        ):
            return order

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)
        self._active_orders.pop(order.order_id, None)
        self._order_history.append(order)
        logger.info("Order cancelled: %s", order.order_id[:8])
        return order

    def expire(self, order: Order) -> Order:
        """Mark an order as expired."""
        order.status = OrderStatus.EXPIRED
        order.updated_at = datetime.now(timezone.utc)
        self._active_orders.pop(order.order_id, None)
        self._order_history.append(order)
        return order

    # ── query ──────────────────────────────────────────────────────────────

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an active or historical order by ID."""
        if order_id in self._active_orders:
            return self._active_orders[order_id]
        for order in self._order_history:
            if order.order_id == order_id:
                return order
        return None

    def get_active_orders(
        self, symbol: Optional[str] = None
    ) -> List[Order]:
        """Get currently active orders, optionally filtered by symbol."""
        orders = list(self._active_orders.values())
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def get_active_order_count(self) -> int:
        """Get the number of active orders."""
        return len(self._active_orders)

    def get_stats(self) -> Dict[str, Any]:
        """Return order simulator statistics."""
        active = list(self._active_orders.values())
        return {
            "active_orders": len(active),
            "total_orders": len(self._order_history) + len(active),
            "by_type": {
                "market": sum(1 for o in active if o.order_type == OrderType.MARKET),
                "limit": sum(1 for o in active if o.order_type == OrderType.LIMIT),
                "stop": sum(1 for o in active if o.order_type == OrderType.STOP),
                "stop_limit": sum(1 for o in active if o.order_type == OrderType.STOP_LIMIT),
            },
        }

    # ── settings ───────────────────────────────────────────────────────────

    def set_limits(
        self,
        min_order_value: float = 0.0,
        max_order_quantity: float = float("inf"),
    ) -> None:
        """Set order size limits."""
        self._min_order_value = min_order_value
        self._max_order_quantity = max_order_quantity
