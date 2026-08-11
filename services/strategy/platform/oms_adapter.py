"""
OMS Adapter — Connects Strategy Platform to the Order Management System.

Provides standardized interface for submitting orders, tracking order
state, and managing the order lifecycle from intent to execution.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OMSOrderState(str, Enum):
    """OMS order lifecycle states."""
    CREATED = "created"
    PENDING = "pending"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    ERROR = "error"


class OrderType(str, Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, Enum):
    """Order sides."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class OMSOrderRequest:
    """Request to submit an order to OMS."""
    strategy_id: str
    instrument: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    intent_id: Optional[str] = None
    time_in_force: str = "DAY"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OMSOrderResult:
    """Result of an OMS order submission."""
    order_id: str
    strategy_id: str
    instrument: str
    side: OrderSide
    quantity: float
    state: OMSOrderState = OMSOrderState.CREATED
    filled_quantity: float = 0.0
    average_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class OMSAdapter:
    """
    Adapter for the Order Management System (OMS).

    Provides a standardized interface for submitting orders from
    strategy order intents, tracking order lifecycle, and managing
    order state transitions.

    Usage::

        adapter = OMSAdapter()
        await adapter.initialize()
        result = await adapter.submit_order(OMSOrderRequest(
            strategy_id="strat_001",
            instrument="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=150.0,
        ))
    """

    def __init__(self) -> None:
        self._orders: dict[str, OMSOrderResult] = {}
        self._counter: int = 0
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the OMS adapter."""
        self._initialized = True
        logger.info("OMSAdapter initialized.")

    async def stop(self) -> None:
        """Stop the adapter."""
        self._initialized = False
        logger.info("OMSAdapter stopped.")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def submit_order(self, request: OMSOrderRequest) -> OMSOrderResult:
        """Submit an order to the OMS."""
        self._counter += 1
        order_id = f"oms_{self._counter:06d}"

        result = OMSOrderResult(
            order_id=order_id,
            strategy_id=request.strategy_id,
            instrument=request.instrument,
            side=request.side,
            quantity=request.quantity,
            state=OMSOrderState.ACCEPTED,
            metadata=request.metadata,
        )
        self._orders[order_id] = result

        logger.info(f"Order submitted: {order_id} {request.side.value} {request.quantity} {request.instrument}")
        return result

    async def get_order(self, order_id: str) -> Optional[OMSOrderResult]:
        """Get an order by ID."""
        return self._orders.get(order_id)

    async def cancel_order(self, order_id: str) -> Optional[OMSOrderResult]:
        """Cancel an open order."""
        order = self._orders.get(order_id)
        if not order:
            return None
        if order.state in (OMSOrderState.CREATED, OMSOrderState.PENDING, OMSOrderState.ACCEPTED, OMSOrderState.PARTIALLY_FILLED):
            order.state = OMSOrderState.CANCELLED
            order.updated_at = datetime.now(timezone.utc)
            logger.info(f"Order cancelled: {order_id}")
        return order

    async def update_order_state(
        self,
        order_id: str,
        state: OMSOrderState,
        filled_quantity: Optional[float] = None,
        average_price: Optional[float] = None,
    ) -> Optional[OMSOrderResult]:
        """Update an order's state."""
        order = self._orders.get(order_id)
        if not order:
            return None
        order.state = state
        order.updated_at = datetime.now(timezone.utc)
        if filled_quantity is not None:
            order.filled_quantity = filled_quantity
        if average_price is not None:
            order.average_price = average_price
        return order

    async def list_orders(
        self,
        strategy_id: Optional[str] = None,
        state: Optional[OMSOrderState] = None,
        limit: int = 100,
    ) -> list[OMSOrderResult]:
        """List orders with optional filters."""
        results = list(self._orders.values())
        if strategy_id:
            results = [o for o in results if o.strategy_id == strategy_id]
        if state:
            results = [o for o in results if o.state == state]
        return sorted(results, key=lambda o: o.created_at, reverse=True)[:limit]

    async def get_open_orders(self, strategy_id: Optional[str] = None) -> list[OMSOrderResult]:
        """Get all open orders, optionally filtered by strategy."""
        open_states = {OMSOrderState.CREATED, OMSOrderState.PENDING, OMSOrderState.ACCEPTED, OMSOrderState.PARTIALLY_FILLED}
        results = [o for o in self._orders.values() if o.state in open_states]
        if strategy_id:
            results = [o for o in results if o.strategy_id == strategy_id]
        return results

    async def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "orders_tracked": len(self._orders),
            "open_orders": len(await self.get_open_orders()),
        }
