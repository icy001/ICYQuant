"""Order Manager.

Central order lifecycle controller. Responsible for:
- Creating orders with validation
- Modifying (replacing) active orders
- Cancelling orders
- Querying order status
- Coordinating with state machine for all transitions

This is the primary interface for managing orders through
their entire lifecycle within the OMS/EMS layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import Order, OrderSide, OrderStatus, OrderType, OrderSource, TimeInForce
from .state_machine import InvalidTransitionError, OrderStateMachine


class OrderValidationError(Exception):
    """Raised when an order fails validation."""

    pass


class OrderNotFoundError(Exception):
    """Raised when an order is not found."""

    pass


class OrderModificationError(Exception):
    """Raised when an order modification fails."""

    pass


class OrderManager:
    """Manages the complete order lifecycle.

    Coordinates order creation, validation, routing, execution
    tracking, and cancellation through the state machine.

    Usage:
        manager = OrderManager()
        order = manager.create_order(
            symbol="NVDA",
            side=OrderSide.BUY,
            quantity=10000,
            strategy_id="AI_Momentum",
        )
        manager.validate_order(order.order_id)
        manager.route_order(order.order_id, broker="IBKR", market="NASDAQ")
        manager.submit_order(order.order_id)
    """

    def __init__(self) -> None:
        self._orders: Dict[str, Order] = {}
        self._state_machine = OrderStateMachine()
        self._counter: int = 0

    # =========================================================================
    # Order Creation
    # =========================================================================

    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float = 0.0,
        order_type: OrderType = OrderType.MARKET,
        strategy_id: str = "",
        time_in_force: TimeInForce = TimeInForce.DAY,
        source: OrderSource = OrderSource.STRATEGY,
        broker: str = "",
        market: str = "",
        tags: Optional[Dict[str, str]] = None,
        notes: str = "",
    ) -> Order:
        """Create a new order.

        Args:
            symbol: Trading symbol (e.g., "NVDA", "AAPL")
            side: BUY or SELL
            quantity: Number of shares/contracts
            price: Limit price (0 for market orders)
            order_type: MARKET, LIMIT, STOP, or STOP_LIMIT
            strategy_id: ID of the originating strategy
            time_in_force: DAY, GTC, IOC, FOK, GTD
            source: Origin of the order
            broker: Target broker
            market: Target market/exchange
            tags: Arbitrary key-value metadata
            notes: Human-readable notes

        Returns:
            The newly created Order object

        Raises:
            OrderValidationError: If order parameters are invalid
        """
        self._validate_create_params(symbol, side, quantity, price, order_type)

        self._counter += 1
        order_id = f"ORD_{datetime.utcnow().strftime('%Y%m%d')}_{self._counter:06d}"

        order = Order(
            order_id=order_id,
            strategy_id=strategy_id,
            symbol=symbol.upper(),
            side=side,
            quantity=quantity,
            price=price,
            status=OrderStatus.CREATED,
            order_type=order_type,
            time_in_force=time_in_force,
            source=source,
            broker=broker,
            market=market,
            tags=tags or {},
            notes=notes,
        )

        self._orders[order.order_id] = order
        order.record_status_change(OrderStatus.CREATED, OrderStatus.CREATED)
        return order

    def _validate_create_params(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
        order_type: OrderType,
    ) -> None:
        """Validate order creation parameters.

        Args:
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Number of shares
            price: Limit price
            order_type: Order type

        Raises:
            OrderValidationError: If any parameter is invalid
        """
        if not symbol or not symbol.strip():
            raise OrderValidationError("Symbol is required")

        if quantity <= 0:
            raise OrderValidationError(f"Quantity must be positive, got {quantity}")

        if order_type == OrderType.LIMIT and price <= 0:
            raise OrderValidationError("Limit orders require a positive price")

        if order_type == OrderType.STOP and price <= 0:
            raise OrderValidationError("Stop orders require a positive price")

        if order_type == OrderType.STOP_LIMIT and price <= 0:
            raise OrderValidationError("Stop-limit orders require a positive price")

    # =========================================================================
    # Order Lifecycle Operations
    # =========================================================================

    def validate_order(self, order_id: str) -> Order:
        """Validate an order (CREATED -> VALIDATED).

        Performs business rule validation before routing.

        Args:
            order_id: Order to validate

        Returns:
            Updated order

        Raises:
            OrderNotFoundError: If order_id not found
            InvalidTransitionError: If order is not in CREATED state
        """
        order = self._get_order(order_id)
        self._state_machine.transition(order, OrderStatus.VALIDATED)
        return order

    def route_order(self, order_id: str, broker: str = "", market: str = "") -> Order:
        """Route an order to a specific broker/market (VALIDATED -> ROUTED).

        Args:
            order_id: Order to route
            broker: Target broker identifier
            market: Target market/exchange identifier

        Returns:
            Updated order

        Raises:
            OrderNotFoundError: If order_id not found
            InvalidTransitionError: If order is not in VALIDATED state
        """
        order = self._get_order(order_id)
        if broker:
            order.broker = broker
        if market:
            order.market = market
        order.route = f"{order.broker}/{order.market}" if order.broker and order.market else order.route
        self._state_machine.transition(order, OrderStatus.ROUTED)
        return order

    def submit_order(self, order_id: str) -> Order:
        """Submit an order to the exchange (ROUTED -> SUBMITTED).

        Args:
            order_id: Order to submit

        Returns:
            Updated order

        Raises:
            OrderNotFoundError: If order_id not found
            InvalidTransitionError: If order is not in ROUTED state
        """
        order = self._get_order(order_id)
        self._state_machine.transition(order, OrderStatus.SUBMITTED)
        return order

    def acknowledge_order(self, order_id: str) -> Order:
        """Acknowledge order receipt by broker (SUBMITTED -> ACKNOWLEDGED).

        Args:
            order_id: Order to acknowledge

        Returns:
            Updated order

        Raises:
            OrderNotFoundError: If order_id not found
            InvalidTransitionError: If order is not in SUBMITTED state
        """
        order = self._get_order(order_id)
        self._state_machine.transition(order, OrderStatus.ACKNOWLEDGED)
        return order

    def fill_order(
        self,
        order_id: str,
        fill_quantity: float,
        fill_price: float,
        commission: float = 0.0,
    ) -> Order:
        """Record a fill on an order.

        Supports partial fills. When total filled equals or exceeds
        order quantity, transitions to FILLED.

        Args:
            order_id: Order being filled
            fill_quantity: Quantity filled in this execution
            fill_price: Execution price for this fill
            commission: Commission charged for this fill

        Returns:
            Updated order

        Raises:
            OrderNotFoundError: If order_id not found
            InvalidTransitionError: If order not in fillable state
            OrderValidationError: If fill quantity is invalid
        """
        order = self._get_order(order_id)

        if fill_quantity <= 0:
            raise OrderValidationError(f"Fill quantity must be positive, got {fill_quantity}")

        if fill_price <= 0:
            raise OrderValidationError(f"Fill price must be positive, got {fill_price}")

        # Update average fill price using weighted average
        total_value = (order.filled_quantity * order.average_fill_price) + (fill_quantity * fill_price)
        order.filled_quantity += fill_quantity
        if order.filled_quantity > 0:
            order.average_fill_price = total_value / order.filled_quantity
        order.total_commission += commission

        if order.filled_quantity >= order.quantity:
            self._state_machine.transition(order, OrderStatus.FILLED)
        else:
            self._state_machine.transition(order, OrderStatus.PARTIALLY_FILLED)

        return order

    def cancel_order(self, order_id: str, reason: str = "") -> Order:
        """Cancel an order.

        Can be cancelled from: CREATED, VALIDATED, SUBMITTED,
        ACKNOWLEDGED, PARTIALLY_FILLED.

        Args:
            order_id: Order to cancel
            reason: Reason for cancellation

        Returns:
            Updated order

        Raises:
            OrderNotFoundError: If order_id not found
            InvalidTransitionError: If order cannot be cancelled
        """
        order = self._get_order(order_id)
        if reason:
            order.notes = (order.notes + "; " if order.notes else "") + f"Cancelled: {reason}"
        self._state_machine.transition(order, OrderStatus.CANCELLED)
        return order

    def reject_order(self, order_id: str, reason: str = "") -> Order:
        """Reject an order.

        Can be rejected from: VALIDATED, ROUTED, SUBMITTED.

        Args:
            order_id: Order to reject
            reason: Reason for rejection

        Returns:
            Updated order

        Raises:
            OrderNotFoundError: If order_id not found
            InvalidTransitionError: If order cannot be rejected
        """
        order = self._get_order(order_id)
        order.rejection_reason = reason or order.rejection_reason
        self._state_machine.transition(order, OrderStatus.REJECTED)
        return order

    # =========================================================================
    # Order Modification
    # =========================================================================

    def replace_order(
        self,
        order_id: str,
        new_quantity: Optional[float] = None,
        new_price: Optional[float] = None,
    ) -> Order:
        """Replace (modify) an active order.

        Only orders in SUBMITTED, ACKNOWLEDGED, or PARTIALLY_FILLED
        states can be modified. The new quantity cannot be less than
        the already-filled quantity.

        Args:
            order_id: Order to modify
            new_quantity: New total quantity (must be >= filled quantity)
            new_price: New limit price

        Returns:
            Updated order

        Raises:
            OrderNotFoundError: If order_id not found
            OrderModificationError: If modification is not allowed
        """
        order = self._get_order(order_id)

        if order.status not in (
            OrderStatus.SUBMITTED,
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.PARTIALLY_FILLED,
        ):
            raise OrderModificationError(
                f"Cannot modify order in {order.status.value} state. "
                f"Only SUBMITTED, ACKNOWLEDGED, or PARTIALLY_FILLED orders can be modified."
            )

        if new_quantity is not None:
            if new_quantity <= 0:
                raise OrderModificationError(f"New quantity must be positive, got {new_quantity}")
            if new_quantity < order.filled_quantity:
                raise OrderModificationError(
                    f"New quantity ({new_quantity}) cannot be less than "
                    f"already-filled quantity ({order.filled_quantity})"
                )
            order.quantity = new_quantity

            # If new quantity matches filled, mark as filled
            if new_quantity == order.filled_quantity and order.filled_quantity > 0:
                self._state_machine.transition(order, OrderStatus.FILLED)

        if new_price is not None:
            if new_price <= 0:
                raise OrderModificationError(f"New price must be positive, got {new_price}")
            order.price = new_price

        order.updated_at = datetime.utcnow()
        return order

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID.

        Args:
            order_id: Order identifier

        Returns:
            Order if found, None otherwise
        """
        return self._orders.get(order_id)

    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """Get the current status of an order.

        Args:
            order_id: Order identifier

        Returns:
            OrderStatus if found, None otherwise
        """
        order = self._orders.get(order_id)
        return order.status if order else None

    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """Get all orders for a given symbol.

        Args:
            symbol: Trading symbol

        Returns:
            List of matching orders
        """
        return [o for o in self._orders.values() if o.symbol == symbol.upper()]

    def get_orders_by_strategy(self, strategy_id: str) -> List[Order]:
        """Get all orders from a given strategy.

        Args:
            strategy_id: Strategy identifier

        Returns:
            List of matching orders
        """
        return [o for o in self._orders.values() if o.strategy_id == strategy_id]

    def get_orders_by_status(self, status: OrderStatus) -> List[Order]:
        """Get all orders with a given status.

        Args:
            status: Order status to filter by

        Returns:
            List of matching orders
        """
        return [o for o in self._orders.values() if o.status == status]

    def get_active_orders(self) -> List[Order]:
        """Get all currently active orders (in the market).

        Returns:
            List of active orders (SUBMITTED, ACKNOWLEDGED, PARTIALLY_FILLED)
        """
        return [o for o in self._orders.values() if o.is_active]

    def get_all_orders(self) -> List[Order]:
        """Get all orders in the system.

        Returns:
            List of all orders
        """
        return list(self._orders.values())

    def get_order_count(self) -> int:
        """Get total number of orders.

        Returns:
            Order count
        """
        return len(self._orders)

    def get_order_summary(self) -> Dict[str, Any]:
        """Get a summary of all orders by status.

        Returns:
            Dictionary with counts per status and totals
        """
        orders = self._orders.values()
        summary: Dict[str, Any] = {
            "total": len(orders),
            "by_status": {},
            "active": 0,
            "terminal": 0,
        }
        for order in orders:
            status = order.status.value
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            if order.is_active:
                summary["active"] += 1
            if order.is_terminal:
                summary["terminal"] += 1
        return summary

    # =========================================================================
    # Helpers
    # =========================================================================

    def _get_order(self, order_id: str) -> Order:
        """Get an order or raise OrderNotFoundError.

        Args:
            order_id: Order identifier

        Returns:
            The order

        Raises:
            OrderNotFoundError: If order not found
        """
        order = self._orders.get(order_id)
        if order is None:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        return order
