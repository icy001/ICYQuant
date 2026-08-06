"""Order Adapter — OMS integration for workflow-driven order management.

The :class:`OrderAdapter` bridges workflow execution with the Order Management
System, enabling workflows to create, modify, and cancel orders.

Architecture::

    Workflow → OMS → Risk → Execution → Settlement → Ledger
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    RISK_CHECKING = "RISK_CHECKING"
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REJECTED = "RISK_REJECTED"
    EXECUTING = "EXECUTING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


@dataclass
class OrderRequest:
    """A request to create an order through the workflow."""

    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "account": self.account,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
        }


@dataclass
class OrderResponse:
    """The result of an order operation."""

    order_id: str
    status: OrderStatus = OrderStatus.CREATED
    filled_quantity: float = 0.0
    avg_price: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status not in (OrderStatus.REJECTED, OrderStatus.FAILED)


class OrderAdapter:
    """Bridges workflow execution with the OMS.

    Usage::

        adapter = OrderAdapter()
        await adapter.start()
        req = OrderRequest(account="ACC001", symbol="AAPL", side=OrderSide.BUY, quantity=100)
        resp = await adapter.create_order(req)
    """

    def __init__(self) -> None:
        self._lock = __import__("threading").RLock()
        self._started = False
        self._orders: Dict[str, OrderResponse] = {}
        self._on_order_update_callbacks: list = []

    async def start(self) -> None:
        self._started = True
        logger.info("OrderAdapter: started")

    async def stop(self) -> None:
        self._started = False
        logger.info("OrderAdapter: stopped")

    # ------------------------------------------------------------------
    # Order operations
    # ------------------------------------------------------------------

    async def create_order(self, request: OrderRequest) -> OrderResponse:
        """Create a new order."""
        logger.info("OrderAdapter: creating order %s (%s %s %s x%.0f)",
                     request.order_id, request.side.value, request.symbol, request.order_type.value, request.quantity)
        resp = OrderResponse(order_id=request.order_id, status=OrderStatus.CREATED)
        with self._lock:
            self._orders[request.order_id] = resp
        return resp

    async def modify_order(self, order_id: str, *, quantity: Optional[float] = None, price: Optional[float] = None) -> Optional[OrderResponse]:
        """Modify an existing order."""
        with self._lock:
            order = self._orders.get(order_id)
            if order:
                order.metadata["modified"] = True
                return order
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        with self._lock:
            order = self._orders.get(order_id)
            if order:
                order.status = OrderStatus.CANCELLED
                return True
            return False

    async def get_order(self, order_id: str) -> Optional[OrderResponse]:
        with self._lock:
            return self._orders.get(order_id)

    async def list_orders(
        self,
        *,
        account: Optional[str] = None,
        status: Optional[OrderStatus] = None,
    ) -> List[OrderResponse]:
        with self._lock:
            results = list(self._orders.values())
            if account:
                results = [o for o in results if o.metadata.get("account") == account]
            if status:
                results = [o for o in results if o.status == status]
            return results

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_order_update(self, callback) -> None:
        self._on_order_update_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active_orders": len(self._orders),
                "by_status": {},
            }
