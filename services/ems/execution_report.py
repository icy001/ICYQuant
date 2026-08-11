"""Execution Report — Post-execution reporting and analysis.

Generates comprehensive execution reports including fill details,
quality metrics, and algorithm performance analysis.

Report Types:
    - Summary: High-level execution overview
    - Detailed: Full fill-by-fill breakdown
    - Quality: Execution quality analysis
    - Comparison: Multi-algorithm comparison

Usage::

    report = ExecutionReport(
        task_id="EXEC_001",
        parent_order_id="PO_001",
        status=ExecutionStatus.COMPLETED,
        child_orders=children,
        duration_seconds=3600.0,
    )
    summary = report.generate_summary()
    detailed = report.generate_detailed()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.ems.child_order import ChildOrder, ChildOrderStatus
from services.ems.execution_state import ExecutionStatus

logger = logging.getLogger(__name__)


@dataclass
class ExecutionReport:
    """Post-execution report with fill details and quality metrics.

    Attributes:
        task_id: Execution task identifier
        parent_order_id: Parent order identifier
        status: Final execution status
        child_orders: All child orders for this execution
        duration_seconds: Total execution duration
        generated_at: Report generation time
        metadata: Additional report metadata
    """

    task_id: str = ""
    parent_order_id: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    child_orders: list[ChildOrder] = field(default_factory=list)
    duration_seconds: float = 0.0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_quantity(self) -> float:
        """Total quantity across all child orders."""
        return sum(c.quantity for c in self.child_orders)

    @property
    def filled_quantity(self) -> float:
        """Total filled quantity."""
        return sum(c.filled_quantity for c in self.child_orders)

    @property
    def remaining_quantity(self) -> float:
        """Total remaining quantity."""
        return sum(c.remaining_quantity for c in self.child_orders)

    @property
    def fill_pct(self) -> float:
        """Overall fill percentage."""
        if self.total_quantity <= 0:
            return 0.0
        return self.filled_quantity / self.total_quantity

    @property
    def average_price(self) -> float:
        """Volume-weighted average execution price."""
        total_notional = sum(
            c.filled_quantity * c.average_price
            for c in self.child_orders
            if c.filled_quantity > 0
        )
        if self.filled_quantity <= 0:
            return 0.0
        return total_notional / self.filled_quantity

    @property
    def total_commission(self) -> float:
        """Total commission paid."""
        return sum(c.commission for c in self.child_orders)

    @property
    def filled_children(self) -> int:
        """Number of fully filled child orders."""
        return sum(1 for c in self.child_orders if c.status == ChildOrderStatus.FILLED)

    @property
    def cancelled_children(self) -> int:
        """Number of cancelled child orders."""
        return sum(1 for c in self.child_orders if c.status == ChildOrderStatus.CANCELLED)

    @property
    def rejected_children(self) -> int:
        """Number of rejected child orders."""
        return sum(1 for c in self.child_orders if c.status == ChildOrderStatus.REJECTED)

    # ── Report Generation ──────────────────────────────────────────

    def generate_summary(self) -> dict[str, Any]:
        """Generate a summary execution report.

        Returns:
            Summary report dictionary
        """
        return {
            "report_type": "summary",
            "task_id": self.task_id,
            "parent_order_id": self.parent_order_id,
            "status": self.status.value,
            "generated_at": self.generated_at.isoformat(),
            "execution": {
                "total_quantity": self.total_quantity,
                "filled_quantity": self.filled_quantity,
                "remaining_quantity": self.remaining_quantity,
                "fill_pct": self.fill_pct,
                "average_price": self.average_price,
                "total_commission": self.total_commission,
                "duration_seconds": self.duration_seconds,
                "fill_rate_per_min": (
                    (self.filled_quantity / self.duration_seconds) * 60
                    if self.duration_seconds > 0
                    else 0.0
                ),
            },
            "children": {
                "total": len(self.child_orders),
                "filled": self.filled_children,
                "cancelled": self.cancelled_children,
                "rejected": self.rejected_children,
                "active": sum(1 for c in self.child_orders if c.status.is_active),
            },
        }

    def generate_detailed(self) -> dict[str, Any]:
        """Generate a detailed fill-by-fill report.

        Returns:
            Detailed report dictionary
        """
        summary = self.generate_summary()

        child_details = []
        for child in sorted(self.child_orders, key=lambda c: c.slice_index):
            child_details.append({
                "order_id": child.order_id,
                "slice_index": child.slice_index,
                "status": child.status.value,
                "quantity": child.quantity,
                "filled_quantity": child.filled_quantity,
                "remaining_quantity": child.remaining_quantity,
                "fill_pct": child.fill_pct,
                "average_price": child.average_price,
                "price": child.price,
                "commission": child.commission,
                "duration_seconds": child.duration_seconds,
                "venue": child.venue,
            })

        summary["report_type"] = "detailed"
        summary["child_orders"] = child_details
        summary["fill_distribution"] = self._compute_fill_distribution()

        return summary

    def generate_quality(self, benchmark_price: float = 0.0) -> dict[str, Any]:
        """Generate an execution quality report.

        Args:
            benchmark_price: Benchmark price for comparison

        Returns:
            Quality report dictionary
        """
        summary = self.generate_summary()

        slippage_bps = 0.0
        if benchmark_price > 0 and self.average_price > 0:
            slippage_bps = (self.average_price - benchmark_price) / benchmark_price * 10000

        # Compute fill time distribution
        fill_times = [
            c.duration_seconds
            for c in self.child_orders
            if c.status == ChildOrderStatus.FILLED
        ]

        summary["report_type"] = "quality"
        summary["quality"] = {
            "benchmark_price": benchmark_price,
            "average_price": self.average_price,
            "slippage_bps": slippage_bps,
            "implementation_shortfall_bps": slippage_bps,  # Simplified
            "fill_count": len(fill_times),
            "avg_fill_time_seconds": sum(fill_times) / len(fill_times) if fill_times else 0.0,
            "max_fill_time_seconds": max(fill_times) if fill_times else 0.0,
            "min_fill_time_seconds": min(fill_times) if fill_times else 0.0,
        }

        return summary

    def _compute_fill_distribution(self) -> dict[str, Any]:
        """Compute fill distribution statistics.

        Returns:
            Distribution statistics dictionary
        """
        filled = [c for c in self.child_orders if c.filled_quantity > 0]
        if not filled:
            return {"count": 0}

        prices = [c.average_price for c in filled if c.average_price > 0]
        quantities = [c.filled_quantity for c in filled]

        return {
            "count": len(filled),
            "price_range": {
                "min": min(prices) if prices else 0.0,
                "max": max(prices) if prices else 0.0,
                "avg": sum(prices) / len(prices) if prices else 0.0,
            },
            "quantity_range": {
                "min": min(quantities) if quantities else 0.0,
                "max": max(quantities) if quantities else 0.0,
                "avg": sum(quantities) / len(quantities) if quantities else 0.0,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize report to dictionary (summary format)."""
        return self.generate_summary()
