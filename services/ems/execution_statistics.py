"""Execution Statistics — Statistical analysis for execution performance.

Computes statistical metrics for execution performance including
mean, median, standard deviation, and percentile distributions.

Usage::

    stats = ExecutionStatistics()
    stats.record_fill(fill_qty=100, fill_price=150.0)
    stats.record_fill(fill_qty=200, fill_price=150.5)
    summary = stats.compute()
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class FillRecord:
    """A single fill record for statistical analysis."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    quantity: float = 0.0
    price: float = 0.0
    commission: float = 0.0
    venue: str = ""


@dataclass
class ExecutionStatisticsSummary:
    """Summary of execution statistics."""

    fill_count: int = 0
    total_quantity: float = 0.0
    total_notional: float = 0.0
    vwap: float = 0.0
    mean_price: float = 0.0
    median_price: float = 0.0
    std_price: float = 0.0
    min_price: float = 0.0
    max_price: float = 0.0
    mean_fill_size: float = 0.0
    median_fill_size: float = 0.0
    total_commission: float = 0.0
    venue_distribution: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fill_count": self.fill_count,
            "total_quantity": self.total_quantity,
            "total_notional": self.total_notional,
            "vwap": self.vwap,
            "mean_price": self.mean_price,
            "median_price": self.median_price,
            "std_price": self.std_price,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "mean_fill_size": self.mean_fill_size,
            "median_fill_size": self.median_fill_size,
            "total_commission": self.total_commission,
            "venue_distribution": self.venue_distribution,
        }


class ExecutionStatistics:
    """Statistical analysis engine for execution performance.

    Collects fill records and computes statistical distributions
    for price, quantity, and venue analysis.

    Attributes:
        _fills: Per-parent-order fill records
        _venue_counts: Per-venue fill counts
    """

    def __init__(self) -> None:
        self._fills: dict[str, list[FillRecord]] = defaultdict(list)

    # ── Recording ──────────────────────────────────────────────────

    def record_fill(
        self,
        parent_order_id: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        venue: str = "",
    ) -> None:
        """Record a fill for statistical analysis.

        Args:
            parent_order_id: Parent order identifier
            quantity: Fill quantity
            price: Fill price
            commission: Commission
            venue: Execution venue
        """
        record = FillRecord(
            quantity=quantity,
            price=price,
            commission=commission,
            venue=venue,
        )
        self._fills[parent_order_id].append(record)

    # ── Computation ────────────────────────────────────────────────

    def compute(self, parent_order_id: str) -> ExecutionStatisticsSummary:
        """Compute execution statistics for a parent order.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            ExecutionStatisticsSummary
        """
        fills = self._fills.get(parent_order_id, [])

        if not fills:
            return ExecutionStatisticsSummary()

        quantities = [f.quantity for f in fills]
        prices = [f.price for f in fills]
        commissions = [f.commission for f in fills]

        total_qty = sum(quantities)
        total_notional = sum(q * p for q, p in zip(quantities, prices))
        total_commission = sum(commissions)

        vwap = total_notional / total_qty if total_qty > 0 else 0.0

        # Price statistics
        sorted_prices = sorted(prices)
        n = len(sorted_prices)

        mean_price = sum(prices) / n if n > 0 else 0.0
        median_price = sorted_prices[n // 2] if n > 0 else 0.0
        min_price = sorted_prices[0] if n > 0 else 0.0
        max_price = sorted_prices[-1] if n > 0 else 0.0

        # Standard deviation
        if n > 1:
            variance = sum((p - mean_price) ** 2 for p in prices) / (n - 1)
            std_price = math.sqrt(variance)
        else:
            std_price = 0.0

        # Fill size statistics
        sorted_qty = sorted(quantities)
        mean_fill = total_qty / n if n > 0 else 0.0
        median_fill = sorted_qty[n // 2] if n > 0 else 0.0

        # Venue distribution
        venue_dist: dict[str, int] = defaultdict(int)
        for f in fills:
            if f.venue:
                venue_dist[f.venue] += 1

        return ExecutionStatisticsSummary(
            fill_count=n,
            total_quantity=total_qty,
            total_notional=total_notional,
            vwap=vwap,
            mean_price=mean_price,
            median_price=median_price,
            std_price=std_price,
            min_price=min_price,
            max_price=max_price,
            mean_fill_size=mean_fill,
            median_fill_size=median_fill,
            total_commission=total_commission,
            venue_distribution=dict(venue_dist),
        )

    def compute_percentiles(
        self, parent_order_id: str, percentiles: list[float] | None = None
    ) -> dict[str, float]:
        """Compute price percentiles for fills.

        Args:
            parent_order_id: Parent order identifier
            percentiles: List of percentile values (0-100), defaults to [50, 75, 90, 95, 99]

        Returns:
            Dict mapping percentile name to price value
        """
        if percentiles is None:
            percentiles = [50, 75, 90, 95, 99]

        fills = self._fills.get(parent_order_id, [])
        if not fills:
            return {}

        prices = sorted(f.price for f in fills)
        n = len(prices)

        result: dict[str, float] = {}
        for pct in percentiles:
            idx = int(math.ceil(n * pct / 100.0)) - 1
            idx = max(0, min(idx, n - 1))
            result[f"p{pct}"] = prices[idx]

        return result

    # ── Aggregation ────────────────────────────────────────────────

    def compute_aggregate(self) -> ExecutionStatisticsSummary:
        """Compute aggregate statistics across all parent orders.

        Returns:
            Aggregated ExecutionStatisticsSummary
        """
        all_fills: list[FillRecord] = []
        for fills in self._fills.values():
            all_fills.extend(fills)

        if not all_fills:
            return ExecutionStatisticsSummary()

        quantities = [f.quantity for f in all_fills]
        prices = [f.price for f in all_fills]

        total_qty = sum(quantities)
        total_notional = sum(q * p for q, p in zip(quantities, prices))

        sorted_prices = sorted(prices)
        n = len(sorted_prices)

        mean_price = sum(prices) / n if n > 0 else 0.0
        vwap = total_notional / total_qty if total_qty > 0 else 0.0

        venue_dist: dict[str, int] = defaultdict(int)
        for f in all_fills:
            if f.venue:
                venue_dist[f.venue] += 1

        return ExecutionStatisticsSummary(
            fill_count=n,
            total_quantity=total_qty,
            total_notional=total_notional,
            vwap=vwap,
            mean_price=mean_price,
            median_price=sorted_prices[n // 2] if n > 0 else 0.0,
            min_price=sorted_prices[0] if n > 0 else 0.0,
            max_price=sorted_prices[-1] if n > 0 else 0.0,
            venue_distribution=dict(venue_dist),
        )

    # ── Cleanup ────────────────────────────────────────────────────

    def clear(self, parent_order_id: str) -> None:
        """Clear statistics for a parent order.

        Args:
            parent_order_id: Parent order identifier
        """
        self._fills.pop(parent_order_id, None)

    def to_dict(self) -> dict[str, Any]:
        """Serialize statistics state."""
        return {
            "parents": len(self._fills),
            "total_fills": sum(len(v) for v in self._fills.values()),
        }
