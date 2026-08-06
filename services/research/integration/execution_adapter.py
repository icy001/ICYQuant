"""Execution Adapter — bridges Research Platform to the Execution Engine.

Commit 11 Part 1.5: Provides order execution simulation and live execution
capabilities for backtesting and paper trading.

Architecture::

    Signal → Order Generator → Execution Engine → Fill Report

Supports:
    - Simulated execution (backtesting)
    - Paper trading execution
    - Live execution gateway (reserved)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ExecutionAdapterState(str, Enum):
    """Execution adapter lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ExecutionMode(str, Enum):
    """Execution modes."""

    SIMULATED = "simulated"
    PAPER = "paper"
    LIVE = "live"


class OrderSide(str, Enum):
    """Order sides."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class ExecutionAdapter:
    """Adapter for integrating Research Platform with Execution Engine.

    Manages order routing, execution simulation, and fill reporting
    for research workflows.

    Usage::

        adapter = ExecutionAdapter(config={"execution_url": "..."})
        await adapter.initialize()
        order = await adapter.submit_order(
            symbol="AAPL", side=OrderSide.BUY, quantity=100,
            order_type=OrderType.MARKET, mode=ExecutionMode.SIMULATED,
        )
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        adapter_id: Optional[str] = None,
    ) -> None:
        self._id: str = adapter_id or f"exa-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._state: ExecutionAdapterState = ExecutionAdapterState.UNINITIALIZED
        self._created_at: datetime = datetime.now(timezone.utc)

        # Execution engine connection
        self._execution_url: str = self._config.get("execution_url", "http://localhost:8500")
        self._execution_connected: bool = False

        # Order & fill tracking
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._fills: Dict[str, List[Dict[str, Any]]] = {}
        self._default_mode: ExecutionMode = ExecutionMode.SIMULATED

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> ExecutionAdapterState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._execution_connected

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize execution adapter."""
        self._state = ExecutionAdapterState.INITIALIZING
        logger.info("Initializing ExecutionAdapter [%s] → %s", self._id, self._execution_url)

        try:
            await self._connect()
            self._execution_connected = True
            self._state = ExecutionAdapterState.CONNECTED
        except Exception as exc:
            logger.error("Failed to connect to Execution Engine: %s", exc)
            self._state = ExecutionAdapterState.ERROR
            raise

        logger.info("ExecutionAdapter initialized [%s]", self._id)

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize with the Execution Engine."""
        return {
            "adapter_id": self._id,
            "execution_connected": self._execution_connected,
            "open_orders": sum(1 for o in self._orders.values() if o["status"] == "open"),
            "total_orders": len(self._orders),
        }

    async def shutdown(self) -> None:
        """Disconnect from execution engine and clean up."""
        logger.info("Shutting down ExecutionAdapter [%s]...", self._id)
        self._orders.clear()
        self._fills.clear()
        self._execution_connected = False
        self._state = ExecutionAdapterState.UNINITIALIZED

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        """Establish connection to Execution Engine."""
        logger.info("Connecting to Execution Engine at %s", self._execution_url)
        await asyncio.sleep(0.01)
        logger.info("Connected to Execution Engine")

    # ------------------------------------------------------------------
    # Order Management
    # ------------------------------------------------------------------

    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        *,
        price: Optional[float] = None,
        mode: ExecutionMode = ExecutionMode.SIMULATED,
    ) -> Dict[str, Any]:
        """Submit an order for execution.

        Args:
            symbol: Trading symbol.
            side: Buy or sell.
            quantity: Order quantity.
            order_type: Market, limit, stop, stop_limit.
            price: Limit/stop price (required for non-market orders).
            mode: Execution mode.

        Returns:
            Order details including ID and status.
        """
        order_id = f"ord-{uuid4().hex[:16]}"
        order = {
            "id": order_id,
            "symbol": symbol,
            "side": side.value,
            "quantity": quantity,
            "order_type": order_type.value,
            "price": price,
            "mode": mode.value,
            "status": "open",
            "filled_quantity": 0.0,
            "avg_fill_price": None,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        self._orders[order_id] = order

        # Simulate fill for market orders in simulated mode
        if mode == ExecutionMode.SIMULATED and order_type == OrderType.MARKET:
            await self._simulate_fill(order_id)

        logger.info("Order submitted: %s %s %s %.2f", order_id, side.value, symbol, quantity)
        return dict(order)

    async def cancel_order(self, order_id: str) -> None:
        """Cancel an open order."""
        order = self._orders.get(order_id)
        if order is None:
            raise KeyError(f"Order not found: {order_id}")
        if order["status"] != "open":
            raise RuntimeError(f"Order cannot be cancelled: status={order['status']}")
        order["status"] = "cancelled"
        order["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("Order cancelled: %s", order_id)

    async def _simulate_fill(self, order_id: str) -> None:
        """Simulate order fill for backtesting."""
        order = self._orders[order_id]
        fill_price = order.get("price") or 100.0  # use limit price or market price
        fill = {
            "fill_id": f"fill-{uuid4().hex[:16]}",
            "order_id": order_id,
            "quantity": order["quantity"],
            "price": fill_price,
            "filled_at": datetime.now(timezone.utc).isoformat(),
        }
        if order_id not in self._fills:
            self._fills[order_id] = []
        self._fills[order_id].append(fill)

        order["filled_quantity"] = order["quantity"]
        order["avg_fill_price"] = fill_price
        order["status"] = "filled"
        order["filled_at"] = fill["filled_at"]

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """Get order details."""
        order = self._orders.get(order_id)
        if order is None:
            raise KeyError(f"Order not found: {order_id}")
        return dict(order)

    async def get_fills(self, order_id: str) -> List[Dict[str, Any]]:
        """Get fills for an order."""
        return list(self._fills.get(order_id, []))

    async def list_orders(
        self,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List orders with optional filtering."""
        orders = list(self._orders.values())
        if status:
            orders = [o for o in orders if o["status"] == status]
        if symbol:
            orders = [o for o in orders if o["symbol"] == symbol]
        return [dict(o) for o in orders]
