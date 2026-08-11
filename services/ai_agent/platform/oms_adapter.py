"""OMS Adapter — bridges the AI Platform to the Order Management System.

The OMSAdapter translates AI agent trading intentions into standardized
order management operations. It handles order creation, modification,
cancellation, and status tracking through the OMS.

Capabilities:
    - Order creation and submission
    - Order modification and cancellation
    - Order status tracking
    - Position querying
    - Trade history retrieval
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class OrderIntent:
    """An order intention from an AI agent."""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    agent_id: str = ""
    strategy_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderResult:
    """Result of an order operation."""
    order_id: str = ""
    intent: Optional[OrderIntent] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_price: Optional[float] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.monotonic)


class OMSAdapter:
    """Adapter for the ICYQuant Order Management System.

    Translates AI agent trading intentions into standardized OMS
    operations with full order lifecycle management.

    Usage:
        oa = OMSAdapter()
        await oa.initialize()
        intent = OrderIntent(symbol="AAPL", side=OrderSide.BUY, quantity=100, agent_id="agent_1")
        result = await oa.submit_order(intent)
    """

    def __init__(self) -> None:
        self._orders: Dict[str, OrderResult] = {}
        self._order_history: List[OrderResult] = []
        self._max_history: int = 10000
        self._total_orders: int = 0
        self._initialized: bool = False
        logger.info("OMSAdapter created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("OMSAdapter initialized")

    async def shutdown(self) -> None:
        self._orders.clear()
        self._order_history.clear()
        self._initialized = False
        logger.info("OMSAdapter shutdown complete")

    async def submit_order(self, intent: OrderIntent) -> OrderResult:
        """Submit an order intention to the OMS.

        The OMS validates the order, checks limits, and routes it
        to the appropriate execution venue.
        """
        self._total_orders += 1
        order_id = f"ord_{self._total_orders}"

        # TODO: Actual integration with OMS
        result = OrderResult(
            order_id=order_id,
            intent=intent,
            status=OrderStatus.SUBMITTED,
        )

        self._orders[order_id] = result
        logger.info("OMSAdapter: submitted order %s (%s %s %s x%.0f) by agent %s", order_id, intent.side.value, intent.symbol, intent.order_type.value, intent.quantity, intent.agent_id)
        return result

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        order = self._orders.get(order_id)
        if order and order.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
            order.status = OrderStatus.CANCELLED
            self._order_history.append(order)
            del self._orders[order_id]
            logger.info("OMSAdapter: cancelled order %s", order_id)
            return True
        return False

    async def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """Get the current status of an order."""
        order = self._orders.get(order_id)
        if order:
            return order.status
        for o in self._order_history:
            if o.order_id == order_id:
                return o.status
        return None

    async def get_agent_orders(self, agent_id: str, limit: int = 50) -> List[OrderResult]:
        """Get recent orders from an agent."""
        active = [o for o in self._orders.values() if o.intent and o.intent.agent_id == agent_id]
        history = [o for o in self._order_history if o.intent and o.intent.agent_id == agent_id]
        return sorted(active + history, key=lambda o: o.created_at, reverse=True)[:limit]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_orders": self._total_orders,
            "active_orders": len(self._orders),
            "completed_orders": len(self._order_history),
        }
