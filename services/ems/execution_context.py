"""Execution Context — Immutable context passed through the execution pipeline.

Encapsulates all contextual information needed during order execution,
including market data, risk limits, and execution parameters.

Pipeline:
    OMS Order → ExecutionContext → ExecutionEngine → Algorithm → Broker

Usage::

    ctx = ExecutionContext(
        parent_order=order,
        strategy="TWAP",
        duration_seconds=3600,
        max_slippage_bps=5.0,
    )
    engine.execute(ctx)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.oms.order.models import Order


@dataclass
class ExecutionContext:
    """Immutable execution context for the execution pipeline.

    Attributes:
        parent_order: The original OMS order to execute
        strategy: Algorithm strategy name (TWAP, VWAP, POV, etc.)
        duration_seconds: Total execution duration in seconds
        start_time: Scheduled start time (None = immediate)
        end_time: Scheduled end time (None = computed from duration)
        max_slippage_bps: Maximum allowed slippage in basis points
        participation_rate: Target market participation rate (0-1, for POV)
        visible_quantity: Visible display quantity (for Iceberg)
        min_slice_quantity: Minimum quantity per child order
        max_slice_quantity: Maximum quantity per child order
        slice_count: Number of slices (for TWAP)
        price_limit: Maximum/minimum price limit
        venue: Target execution venue
        broker: Target broker
        risk_limits: Risk limits from Risk Platform
        strategy_params: Additional strategy-specific parameters
        metadata: Arbitrary metadata for tracking
    """

    parent_order: Order
    strategy: str = "TWAP"
    duration_seconds: float = 3600.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    max_slippage_bps: float = 10.0
    participation_rate: float = 0.05
    visible_quantity: float = 0.0
    min_slice_quantity: float = 1.0
    max_slice_quantity: float = 0.0
    slice_count: int = 0
    price_limit: Optional[float] = None
    venue: str = ""
    broker: str = ""
    risk_limits: dict[str, Any] = field(default_factory=dict)
    strategy_params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_quantity(self) -> float:
        """Total order quantity to execute."""
        return self.parent_order.quantity

    @property
    def remaining_quantity(self) -> float:
        """Remaining quantity to execute."""
        return self.parent_order.remaining_quantity

    @property
    def effective_duration(self) -> float:
        """Effective duration in seconds."""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return self.duration_seconds

    @property
    def slice_interval_seconds(self) -> float:
        """Interval between slices for time-based algorithms."""
        if self.slice_count <= 0:
            count = max(1, int(self.effective_duration / 60))  # default: 1 min slices
        else:
            count = self.slice_count
        return self.effective_duration / count

    @property
    def effective_slice_quantity(self) -> float:
        """Quantity per slice."""
        if self.slice_count <= 0:
            count = max(1, int(self.effective_duration / 60))
        else:
            count = self.slice_count
        return self.total_quantity / count

    def validate(self) -> list[str]:
        """Validate the execution context.

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[str] = []
        if self.total_quantity <= 0:
            errors.append("Total quantity must be positive")
        if self.duration_seconds <= 0:
            errors.append("Duration must be positive")
        if self.participation_rate <= 0 or self.participation_rate > 1:
            errors.append("Participation rate must be between 0 and 1")
        if self.max_slippage_bps < 0:
            errors.append("Max slippage must be non-negative")
        if not self.strategy:
            errors.append("Strategy name is required")
        return errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize context to dictionary."""
        return {
            "parent_order_id": self.parent_order.order_id,
            "strategy": self.strategy,
            "duration_seconds": self.duration_seconds,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "max_slippage_bps": self.max_slippage_bps,
            "participation_rate": self.participation_rate,
            "visible_quantity": self.visible_quantity,
            "min_slice_quantity": self.min_slice_quantity,
            "max_slice_quantity": self.max_slice_quantity,
            "slice_count": self.slice_count,
            "price_limit": self.price_limit,
            "venue": self.venue,
            "broker": self.broker,
            "total_quantity": self.total_quantity,
            "effective_duration": self.effective_duration,
            "slice_interval_seconds": self.slice_interval_seconds,
            "effective_slice_quantity": self.effective_slice_quantity,
            "strategy_params": self.strategy_params,
            "metadata": self.metadata,
        }
