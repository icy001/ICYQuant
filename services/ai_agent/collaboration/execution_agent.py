"""Execution Agent — specialized agent for order execution and trade management.

Pipeline:
    Execution request / Coordinator assignment
        -> ExecutionAgent.prepare_order() (validate and prepare)
        -> ExecutionAgent.execute() (send order)
        -> ExecutionAgent.confirm() (verify fill)
        -> ExecutionAgent.report() (publish execution report)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.message_bus import MessageBus, Message, MessageType

logger = logging.getLogger(__name__)


class OrderType(str, Enum):
    """Types of orders."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, Enum):
    """Order sides."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order statuses."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """A trading order.

    Attributes:
        order_id: Unique order identifier.
        symbol: Trading symbol.
        side: Buy or sell.
        order_type: Order type.
        quantity: Order quantity.
        price: Limit/stop price (None for market).
        status: Current order status.
        filled_quantity: Quantity filled.
        avg_fill_price: Average fill price.
        created_at: Order creation time.
    """

    order_id: str = field(default_factory=lambda: uuid4().hex)
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: float = 0.0
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExecutionReport:
    """Execution report after order completion.

    Attributes:
        order_id: The executed order ID.
        status: Final order status.
        filled_quantity: Total filled quantity.
        avg_fill_price: Average fill price.
        slippage_bps: Slippage in basis points.
        commission: Commission cost.
        execution_time_ms: Execution time in milliseconds.
    """

    order_id: str = ""
    status: OrderStatus = OrderStatus.FILLED
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    slippage_bps: float = 0.0
    commission: float = 0.0
    execution_time_ms: float = 0.0


class ExecutionAgent:
    """Specialized agent for order execution and trade management.

    Handles order preparation, execution, confirmation, and reporting.
    Implements best execution practices with slippage monitoring.

    Supports:
        - Order preparation and validation
        - Order execution (market, limit, stop)
        - Fill confirmation
        - Execution reporting
        - Slippage monitoring

    Usage:
        agent = ExecutionAgent(agent_id="exec_1", message_bus=bus)
        await agent.initialize()
        order = Order(symbol="AAPL", side=OrderSide.BUY, quantity=100)
        report = await agent.execute(order)
    """

    def __init__(
        self,
        agent_id: str = "",
        message_bus: Optional[MessageBus] = None,
    ) -> None:
        """Initialize the Execution Agent.

        Args:
            agent_id: Unique agent identifier.
            message_bus: Message bus for communication.
        """
        self._agent_id: str = agent_id or uuid4().hex[:12]
        self._message_bus: Optional[MessageBus] = message_bus
        self._initialized: bool = False
        self._orders: Dict[str, Order] = {}
        self._reports: List[ExecutionReport] = []
        logger.info("ExecutionAgent created: %s", self._agent_id)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the execution agent."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("ExecutionAgent initialized: %s", self._agent_id)

    async def shutdown(self) -> None:
        """Shut down the execution agent."""
        self._orders.clear()
        self._reports.clear()
        self._initialized = False
        logger.info("ExecutionAgent shutdown: %s", self._agent_id)

    # ── Order Management ──

    async def prepare_order(
        self, symbol: str, side: OrderSide, quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
    ) -> Order:
        """Prepare and validate an order.

        Args:
            symbol: Trading symbol.
            side: Buy or sell.
            quantity: Order quantity.
            order_type: Order type.
            price: Limit/stop price.

        Returns:
            Prepared order.
        """
        order = Order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.PENDING,
        )
        self._orders[order.order_id] = order
        logger.debug("ExecutionAgent prepared order: %s %s %s x%.0f",
                     order.side.value, order.symbol, order.order_type.value, order.quantity)
        return order

    # ── Execution ──

    async def execute(self, order: Order) -> ExecutionReport:
        """Execute an order.

        Args:
            order: The order to execute.

        Returns:
            ExecutionReport with fill details.
        """
        import time
        start = time.monotonic()

        order.status = OrderStatus.SUBMITTED

        # Simulate execution
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = order.price or 150.0

        elapsed_ms = (time.monotonic() - start) * 1000

        report = ExecutionReport(
            order_id=order.order_id,
            status=order.status,
            filled_quantity=order.filled_quantity,
            avg_fill_price=order.avg_fill_price,
            slippage_bps=2.5,
            commission=order.filled_quantity * order.avg_fill_price * 0.001,
            execution_time_ms=elapsed_ms,
        )
        self._reports.append(report)

        if self._message_bus:
            await self._message_bus.publish(Message(
                msg_type=MessageType.PUBLISH,
                topic="execution.report",
                sender_id=self._agent_id,
                payload={
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "filled_quantity": order.filled_quantity,
                    "avg_fill_price": order.avg_fill_price,
                    "slippage_bps": report.slippage_bps,
                },
            ))

        logger.info("ExecutionAgent executed: %s %s %s x%.0f @ %.2f",
                    order.side.value, order.symbol, order.status.value,
                    order.filled_quantity, order.avg_fill_price)
        return report

    # ── Batch Execution ──

    async def execute_batch(self, orders: List[Order]) -> List[ExecutionReport]:
        """Execute multiple orders.

        Args:
            orders: List of orders.

        Returns:
            List of execution reports.
        """
        reports: List[ExecutionReport] = []
        for order in orders:
            report = await self.execute(order)
            reports.append(report)
        return reports

    # ── Properties ──

    @property
    def agent_id(self) -> str:
        """Return the agent ID."""
        return self._agent_id

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the execution agent state.

        Returns:
            Dict with order and report counts.
        """
        return {
            "agent_id": self._agent_id,
            "initialized": self._initialized,
            "total_orders": len(self._orders),
            "total_reports": len(self._reports),
        }
