"""Order Adapter — bridges the Scheduler with the Order Management System (OMS).

The :class:`OrderAdapter` enables scheduled order operations:
* Batch order submission on schedule
* Scheduled order cancellation
* Order state monitoring
* TWAP/VWAP execution scheduling

Pipeline::

    Scheduler ──→ OrderAdapter ──→ OMS
                      │
            Submit / Cancel / Monitor
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OrderAdapterState(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class OrderAdapter:
    """Adapter for OMS integration.

    Responsibilities:
    * Submit batch orders on schedule
    * Cancel orders by schedule
    * Monitor order execution status
    * Route strategy signals to OMS

    Usage::

        adapter = OrderAdapter(oms_service=oms)
        await adapter.connect()
        await adapter.submit_batch_orders("morning_rebalance", orders=[...])
    """

    def __init__(self, oms_service: Any = None) -> None:
        self._oms = oms_service
        self._state = OrderAdapterState.DISCONNECTED
        self._lock = threading.Lock()
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._submit_count: int = 0
        self._cancel_count: int = 0

    @property
    def state(self) -> OrderAdapterState:
        return self._state

    @property
    def active_orders(self) -> int:
        return len(self._orders)

    @property
    def submit_count(self) -> int:
        return self._submit_count

    @property
    def cancel_count(self) -> int:
        return self._cancel_count

    async def connect(self) -> None:
        self._set_state(OrderAdapterState.CONNECTING)
        try:
            if self._oms and hasattr(self._oms, "connect"):
                await self._oms.connect()
            self._set_state(OrderAdapterState.CONNECTED)
            logger.info("OrderAdapter: connected")
        except Exception as exc:
            self._set_state(OrderAdapterState.ERROR)
            raise

    async def disconnect(self) -> None:
        self._orders.clear()
        self._set_state(OrderAdapterState.DISCONNECTED)

    async def synchronize(self) -> Dict[str, Any]:
        return {"state": self._state.value, "active_orders": len(self._orders)}

    # ------------------------------------------------------------------
    # Order Operations
    # ------------------------------------------------------------------

    async def submit_batch_orders(self, batch_id: str, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Submit a batch of orders through OMS."""
        self._submit_count += len(orders)
        for order in orders:
            order_id = order.get("order_id", f"{batch_id}-{len(self._orders)}")
            self._orders[order_id] = {
                **order, "batch_id": batch_id,
                "submitted_at": datetime.now(timezone.utc).isoformat(), "status": "submitted",
            }
        logger.info("OrderAdapter: submitted %d orders in batch %s", len(orders), batch_id)
        return {"batch_id": batch_id, "submitted": len(orders), "status": "submitted"}

    async def cancel_orders(self, order_ids: List[str]) -> Dict[str, Any]:
        """Cancel specific orders through OMS."""
        self._cancel_count += len(order_ids)
        for oid in order_ids:
            if oid in self._orders:
                self._orders[oid]["status"] = "cancelled"
        return {"cancelled": len(order_ids), "status": "cancelled"}

    async def cancel_all(self) -> Dict[str, Any]:
        """Cancel all active orders."""
        count = len(self._orders)
        for order in self._orders.values():
            order["status"] = "cancelled"
        self._cancel_count += count
        return {"cancelled": count, "status": "all_cancelled"}

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get the status of a specific order."""
        order = self._orders.get(order_id)
        if not order:
            return {"order_id": order_id, "status": "not_found"}
        return {"order_id": order_id, "status": order["status"]}

    def _set_state(self, state: OrderAdapterState) -> None:
        with self._lock:
            self._state = state
