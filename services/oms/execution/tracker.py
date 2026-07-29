"""Execution Tracker.

Tracks order execution progress in real time. Monitors:
- Fill events and partial fills
- Execution quality vs benchmarks
- Remaining quantity and estimated completion
- Slippage and execution costs

The tracker provides live updates on execution progress:
    100,000 shares order:
    30,000 filled (30%)
    -> 70,000 filled (70%)
    -> 100,000 filled (100%)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# Enums
# =============================================================================


class ExecutionStatus(str, Enum):
    """Current execution status of a tracked order."""

    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class FillEventType(str, Enum):
    """Type of fill event."""

    FULL = "FULL"         # Complete fill
    PARTIAL = "PARTIAL"   # Partial fill
    CANCEL = "CANCEL"     # Cancellation
    REJECT = "REJECT"     # Rejection


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class FillEvent:
    """A single fill (trade execution) event.

    Captures the details of each execution including
    price, quantity, timestamp, and venue.
    """

    order_id: str
    fill_id: str
    quantity: float
    price: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_type: FillEventType = FillEventType.PARTIAL
    venue: str = ""
    commission: float = 0.0
    currency: str = "USD"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionSnapshot:
    """Real-time snapshot of order execution progress.

    Provides a point-in-time view of execution state including
    filled vs remaining quantities, VWAP, and slippage.
    """

    order_id: str
    symbol: str
    side: str
    total_quantity: float
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    fill_pct: float = 0.0
    average_price: float = 0.0
    total_commission: float = 0.0
    slippage_bps: float = 0.0
    status: ExecutionStatus = ExecutionStatus.PENDING
    fill_count: int = 0
    first_fill_at: Optional[datetime] = None
    last_fill_at: Optional[datetime] = None
    venue: str = ""
    estimated_completion: Optional[datetime] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize snapshot to dictionary."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "total_quantity": self.total_quantity,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "fill_pct": f"{self.fill_pct:.1%}",
            "average_price": self.average_price,
            "total_commission": self.total_commission,
            "slippage_bps": self.slippage_bps,
            "status": self.status.value,
            "fill_count": self.fill_count,
            "first_fill_at": self.first_fill_at.isoformat() if self.first_fill_at else None,
            "last_fill_at": self.last_fill_at.isoformat() if self.last_fill_at else None,
            "venue": self.venue,
        }


@dataclass
class ExecutionReport:
    """Final execution report for a completed order.

    Summarizes the entire execution including all fills,
    costs, and quality metrics.
    """

    order_id: str
    symbol: str
    side: str
    total_quantity: float
    filled_quantity: float
    average_price: float
    total_commission: float = 0.0
    total_cost: float = 0.0
    slippage_bps: float = 0.0
    arrival_price: float = 0.0
    vwap: float = 0.0
    execution_time_seconds: float = 0.0
    fill_events: List[FillEvent] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report to dictionary."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "total_quantity": self.total_quantity,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "total_commission": self.total_commission,
            "total_cost": self.total_cost,
            "slippage_bps": self.slippage_bps,
            "arrival_price": self.arrival_price,
            "vwap": self.vwap,
            "execution_time_seconds": self.execution_time_seconds,
            "status": self.status.value,
            "fill_count": len(self.fill_events),
            "notes": self.notes,
        }


# =============================================================================
# Execution Tracker
# =============================================================================


class ExecutionTracker:
    """Real-time order execution tracker.

    Monitors fill events, computes execution quality metrics,
    and provides live status snapshots for active orders.

    Usage:
        tracker = ExecutionTracker()
        tracker.start_tracking("ORD_001", "NVDA", "BUY", 100000)

        fill = FillEvent(order_id="ORD_001", fill_id="F001", quantity=30000, price=150.0)
        tracker.on_fill(fill)

        snapshot = tracker.get_snapshot("ORD_001")
        print(f"Filled: {snapshot.fill_pct:.1%}")
    """

    def __init__(self) -> None:
        self._fills: Dict[str, List[FillEvent]] = {}
        self._tracking: Dict[str, Dict[str, Any]] = {}

    def start_tracking(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        arrival_price: float = 0.0,
        venue: str = "",
    ) -> None:
        """Start tracking an order's execution.

        Args:
            order_id: Order to track
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Total order quantity
            arrival_price: Price at order creation time
            venue: Execution venue
        """
        self._fills[order_id] = []
        self._tracking[order_id] = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "arrival_price": arrival_price,
            "venue": venue,
            "started_at": datetime.utcnow(),
        }

    def on_fill(self, fill: FillEvent) -> None:
        """Record a fill event.

        Args:
            fill: Fill event data

        Raises:
            ValueError: If the order is not being tracked
        """
        if fill.order_id not in self._fills:
            raise ValueError(f"Order {fill.order_id} is not being tracked")

        self._fills[fill.order_id].append(fill)

    def stop_tracking(self, order_id: str) -> None:
        """Stop tracking an order (keeps recorded fills).

        Args:
            order_id: Order to stop tracking
        """
        # Data is preserved; just marks the end of active tracking
        pass

    def get_snapshot(self, order_id: str) -> Optional[ExecutionSnapshot]:
        """Get a current execution snapshot.

        Args:
            order_id: Order to query

        Returns:
            Current execution snapshot, or None if not tracked
        """
        info = self._tracking.get(order_id)
        if info is None:
            return None

        fills = self._fills.get(order_id, [])
        filled_qty = sum(f.quantity for f in fills)
        total_commission = sum(f.commission for f in fills)

        # Compute VWAP
        total_value = sum(f.quantity * f.price for f in fills)
        avg_price = total_value / filled_qty if filled_qty > 0 else 0.0

        # Compute slippage vs arrival price
        arrival_price = info["arrival_price"]
        if arrival_price > 0 and avg_price > 0 and info["side"] == "BUY":
            slippage_bps = ((avg_price - arrival_price) / arrival_price) * 10000
        elif arrival_price > 0 and avg_price > 0 and info["side"] == "SELL":
            slippage_bps = ((arrival_price - avg_price) / arrival_price) * 10000
        else:
            slippage_bps = 0.0

        total_qty = info["quantity"]
        fill_pct = filled_qty / total_qty if total_qty > 0 else 0.0

        # Determine status
        if fill_pct >= 1.0:
            status = ExecutionStatus.COMPLETED
        elif filled_qty > 0:
            status = ExecutionStatus.EXECUTING
        else:
            status = ExecutionStatus.PENDING

        return ExecutionSnapshot(
            order_id=order_id,
            symbol=info["symbol"],
            side=info["side"],
            total_quantity=total_qty,
            filled_quantity=filled_qty,
            remaining_quantity=max(0.0, total_qty - filled_qty),
            fill_pct=fill_pct,
            average_price=avg_price,
            total_commission=total_commission,
            slippage_bps=slippage_bps,
            status=status,
            fill_count=len(fills),
            first_fill_at=fills[0].timestamp if fills else None,
            last_fill_at=fills[-1].timestamp if fills else None,
            venue=info["venue"],
        )

    def get_fills(self, order_id: str) -> List[FillEvent]:
        """Get all fill events for an order.

        Args:
            order_id: Order to query

        Returns:
            List of fill events
        """
        return list(self._fills.get(order_id, []))

    def get_report(self, order_id: str) -> Optional[ExecutionReport]:
        """Generate a final execution report.

        Args:
            order_id: Order to report on

        Returns:
            Execution report, or None if not tracked
        """
        snapshot = self.get_snapshot(order_id)
        if snapshot is None:
            return None

        fills = self._fills.get(order_id, [])
        info = self._tracking[order_id]

        total_cost = (snapshot.filled_quantity * snapshot.average_price) + snapshot.total_commission

        # Execution time
        started_at = info["started_at"]
        if fills:
            end_at = fills[-1].timestamp
        else:
            end_at = datetime.utcnow()
        execution_time = (end_at - started_at).total_seconds()

        return ExecutionReport(
            order_id=order_id,
            symbol=snapshot.symbol,
            side=snapshot.side,
            total_quantity=snapshot.total_quantity,
            filled_quantity=snapshot.filled_quantity,
            average_price=snapshot.average_price,
            total_commission=snapshot.total_commission,
            total_cost=total_cost,
            slippage_bps=snapshot.slippage_bps,
            arrival_price=info["arrival_price"],
            vwap=snapshot.average_price,
            execution_time_seconds=execution_time,
            fill_events=fills,
            status=snapshot.status,
        )

    def get_active_orders(self) -> List[str]:
        """Get all currently active order IDs.

        Returns:
            List of order IDs that are still executing
        """
        active = []
        for order_id in self._tracking:
            snapshot = self.get_snapshot(order_id)
            if snapshot and snapshot.status == ExecutionStatus.EXECUTING:
                active.append(order_id)
        return active

    def get_all_snapshots(self) -> List[ExecutionSnapshot]:
        """Get snapshots for all tracked orders.

        Returns:
            List of execution snapshots
        """
        snapshots = []
        for order_id in self._tracking:
            snapshot = self.get_snapshot(order_id)
            if snapshot:
                snapshots.append(snapshot)
        return snapshots
