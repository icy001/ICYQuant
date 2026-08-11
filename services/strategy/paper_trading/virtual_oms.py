"""
Virtual OMS
===========
Virtual Order Management System — accepts paper orders, manages order
lifecycle, and produces fills. Interface mirrors production OMS for
seamless transition from paper to live.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class OmsOrderState(str, Enum):
    """Virtual OMS order states."""
    NEW = "NEW"
    PENDING_NEW = "PENDING_NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    DONE_FOR_DAY = "DONE_FOR_DAY"
    CANCELLED = "CANCELLED"
    REPLACED = "REPLACED"
    PENDING_CANCEL = "PENDING_CANCEL"
    STOPPED = "STOPPED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


@dataclass
class OmsOrder:
    """An order managed by the Virtual OMS."""
    order_id: str = field(default_factory=lambda: f"vo_{uuid4().hex[:12]}")
    cl_ord_id: str = ""       # Client order ID
    instrument: str = ""
    side: str = "BUY"
    quantity: float = 0.0
    order_type: str = "MARKET"
    limit_price: Optional[float] = None
    state: OmsOrderState = OmsOrderState.NEW
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def leaves_quantity(self) -> float:
        return self.quantity - self.filled_quantity

    @property
    def is_complete(self) -> bool:
        return self.state in (
            OmsOrderState.FILLED, OmsOrderState.CANCELLED,
            OmsOrderState.REJECTED, OmsOrderState.DONE_FOR_DAY,
        )


@dataclass
class OmsFill:
    """A single fill from the Virtual OMS."""
    fill_id: str = field(default_factory=lambda: f"vf_{uuid4().hex[:12]}")
    order_id: str = ""
    instrument: str = ""
    side: str = ""
    quantity: float = 0.0
    price: float = 0.0
    commission: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class VirtualOMS:
    """Virtual Order Management System.

    Pipeline:
        Order Intent → Order → Execution → Fill → Portfolio
    """

    def __init__(self):
        self._orders: Dict[str, OmsOrder] = {}
        self._fills: List[OmsFill] = []
        self._execution_simulator: Optional["ExecutionSimulator"] = None
        self._commission_simulator: Optional["CommissionSimulator"] = None
        self.is_initialized = False

    def wire(self, execution_simulator: Optional[Any] = None,
             commission_simulator: Optional[Any] = None) -> None:
        self._execution_simulator = execution_simulator
        self._commission_simulator = commission_simulator

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("VirtualOMS initialized")

    # ------------------------------------------------------------------
    # Order Lifecycle
    # ------------------------------------------------------------------

    async def accept_order(self, paper_order: Any) -> OmsOrder:
        """Accept a paper order and create an OMS order."""
        order = OmsOrder(
            cl_ord_id=getattr(paper_order, 'order_id', ''),
            instrument=getattr(paper_order, 'instrument', ''),
            side=getattr(paper_order, 'side', 'BUY'),
            quantity=getattr(paper_order, 'quantity', 0.0),
            order_type=getattr(paper_order, 'order_type', 'MARKET'),
            limit_price=getattr(paper_order, 'price', None),
            state=OmsOrderState.NEW,
        )
        self._orders[order.order_id] = order
        logger.debug("OMS order accepted: %s", order.order_id)
        return order

    async def execute_order(self, order_id: str) -> List[OmsFill]:
        """Execute an order through the virtual execution pipeline."""
        order = self._orders.get(order_id)
        if not order:
            logger.warning("Unknown order: %s", order_id)
            return []

        order.state = OmsOrderState.PENDING_NEW

        if self._execution_simulator:
            result = await self._execution_simulator.simulate_execution(order)
            fills = []
            for fill_data in result.fills:
                commission = 0.0
                if self._commission_simulator:
                    comm_result = await self._commission_simulator.calculate(
                        fill_data.price, fill_data.quantity
                    )
                    commission = comm_result.commission

                fill = OmsFill(
                    order_id=order_id,
                    instrument=order.instrument,
                    side=order.side,
                    quantity=fill_data.quantity,
                    price=fill_data.price,
                    commission=commission,
                )
                fills.append(fill)
                self._fills.append(fill)

            order.filled_quantity = sum(f.quantity for f in fills)
            if order.filled_quantity > 0:
                order.avg_fill_price = sum(
                    f.quantity * f.price for f in fills
                ) / order.filled_quantity

            if order.filled_quantity >= order.quantity:
                order.state = OmsOrderState.FILLED
            elif order.filled_quantity > 0:
                order.state = OmsOrderState.PARTIALLY_FILLED
            else:
                order.state = OmsOrderState.REJECTED

            order.updated_at = datetime.now(timezone.utc)
            logger.info("Order %s executed: %s fills, state=%s",
                         order_id, len(fills), order.state.value)
            return fills

        # Fallback: full fill at market
        order.state = OmsOrderState.FILLED
        order.filled_quantity = order.quantity
        order.updated_at = datetime.now(timezone.utc)
        logger.debug("Order %s filled (no execution simulator)", order_id)
        return []

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        order = self._orders.get(order_id)
        if not order or order.is_complete:
            return False
        order.state = OmsOrderState.CANCELLED
        order.updated_at = datetime.now(timezone.utc)
        return True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_order(self, order_id: str) -> Optional[OmsOrder]:
        return self._orders.get(order_id)

    def open_orders(self) -> List[OmsOrder]:
        return [o for o in self._orders.values() if not o.is_complete]

    def order_count(self) -> int:
        return len(self._orders)

    def fill_count(self) -> int:
        return len(self._fills)

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_orders": len(self._orders),
            "open_orders": len(self.open_orders()),
            "total_fills": len(self._fills),
            "orders_by_state": {
                state.value: sum(1 for o in self._orders.values() if o.state == state)
                for state in OmsOrderState
            },
        }
