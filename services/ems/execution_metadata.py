"""Execution Metadata — Execution tracking metadata and configuration.

Provides metadata tracking for execution runs, including performance
benchmarks, execution parameters, and audit information.

Usage::

    meta = ExecutionMetadata(
        execution_id="EXEC_001",
        algorithm="TWAP",
        benchmark_price=150.0,
    )
    meta.record_child_order("CHILD_001")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class ExecutionMetadata:
    """Metadata tracking for a single execution run.

    Attributes:
        execution_id: Unique execution identifier
        parent_order_id: Associated parent order ID
        algorithm: Execution algorithm name
        algorithm_version: Algorithm version
        benchmark_price: Arrival/benchmark price at execution start
        target_quantity: Total quantity to execute
        filled_quantity: Cumulative filled quantity
        remaining_quantity: Remaining quantity to execute
        average_price: Volume-weighted average execution price
        total_commission: Total commission paid
        child_orders_total: Total child orders created
        child_orders_filled: Child orders fully filled
        child_orders_active: Currently active child orders
        child_order_ids: List of all child order IDs
        started_at: Execution start time
        completed_at: Execution completion time
        tags: Arbitrary key-value tags
        custom: Arbitrary custom metadata
    """

    execution_id: str = ""
    parent_order_id: str = ""
    algorithm: str = ""
    algorithm_version: str = "1.0.0"
    benchmark_price: float = 0.0
    target_quantity: float = 0.0
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    average_price: float = 0.0
    total_commission: float = 0.0
    child_orders_total: int = 0
    child_orders_filled: int = 0
    child_orders_active: int = 0
    child_order_ids: list[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tags: dict[str, str] = field(default_factory=dict)
    custom: dict[str, Any] = field(default_factory=dict)

    @property
    def fill_pct(self) -> float:
        """Percentage of target quantity filled."""
        if self.target_quantity <= 0:
            return 0.0
        return self.filled_quantity / self.target_quantity

    @property
    def is_complete(self) -> bool:
        """Whether execution is complete."""
        return self.completed_at is not None

    @property
    def duration_seconds(self) -> float:
        """Total execution duration in seconds."""
        if not self.started_at:
            return 0.0
        end = self.completed_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    @property
    def fill_rate_per_minute(self) -> float:
        """Average fill rate in quantity per minute."""
        duration = self.duration_seconds
        if duration <= 0:
            return 0.0
        return (self.filled_quantity / duration) * 60

    def record_child_order(self, child_order_id: str) -> None:
        """Record creation of a new child order.

        Args:
            child_order_id: Child order identifier
        """
        self.child_orders_total += 1
        self.child_orders_active += 1
        if child_order_id not in self.child_order_ids:
            self.child_order_ids.append(child_order_id)

    def record_child_filled(self, child_order_id: str) -> None:
        """Record completion of a child order.

        Args:
            child_order_id: Child order identifier
        """
        self.child_orders_filled += 1
        self.child_orders_active = max(0, self.child_orders_active - 1)

    def record_child_cancelled(self, child_order_id: str) -> None:
        """Record cancellation of a child order.

        Args:
            child_order_id: Child order identifier
        """
        self.child_orders_active = max(0, self.child_orders_active - 1)

    def apply_fill(self, fill_qty: float, fill_price: float, commission: float = 0.0) -> None:
        """Apply a fill to cumulative execution metrics.

        Uses weighted average price calculation for multiple fills.

        Args:
            fill_qty: Fill quantity
            fill_price: Fill price
            commission: Commission for this fill
        """
        if fill_qty <= 0:
            return

        total_notional = self.average_price * self.filled_quantity
        new_notional = fill_qty * fill_price

        self.filled_quantity += fill_qty
        self.remaining_quantity = max(0.0, self.target_quantity - self.filled_quantity)
        self.total_commission += commission

        if self.filled_quantity > 0:
            self.average_price = (total_notional + new_notional) / self.filled_quantity

    def start(self) -> None:
        """Mark execution as started."""
        self.started_at = datetime.now(timezone.utc)

    def complete(self) -> None:
        """Mark execution as completed."""
        self.completed_at = datetime.now(timezone.utc)
        self.child_orders_active = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize metadata to dictionary."""
        return {
            "execution_id": self.execution_id,
            "parent_order_id": self.parent_order_id,
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "benchmark_price": self.benchmark_price,
            "target_quantity": self.target_quantity,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "average_price": self.average_price,
            "total_commission": self.total_commission,
            "fill_pct": self.fill_pct,
            "child_orders_total": self.child_orders_total,
            "child_orders_filled": self.child_orders_filled,
            "child_orders_active": self.child_orders_active,
            "child_order_ids": self.child_order_ids,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "fill_rate_per_minute": self.fill_rate_per_minute,
            "tags": self.tags,
            "custom": self.custom,
        }
