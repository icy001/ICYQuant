"""
Fill Analyzer — detailed fill event analysis.

Analyzes individual fills for:
    - Fill rate (filled / targeted)
    - Price improvement (vs limit)
    - Fill time distribution
    - Partial fill patterns
    - Venue-specific performance
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class FillEvent:
    """A single fill event."""
    fill_id: str = ""
    order_id: str = ""
    quantity: int = 0
    price: float = 0.0
    timestamp: Optional[datetime] = None
    venue: str = ""


@dataclass
class FillAnalysis:
    """Fill analysis result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    total_filled: int = 0
    total_target: int = 0
    fill_rate: float = 0.0
    avg_fill_price: float = 0.0
    arrival_price: float = 0.0
    limit_price: Optional[float] = None
    price_improvement_bps: float = 0.0
    num_fills: int = 0
    avg_fill_size: float = 0.0
    time_to_first_fill_seconds: float = 0.0
    time_to_completion_seconds: float = 0.0
    partial_fill_ratio: float = 0.0
    venue_fills: dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class FillAnalyzer:
    """
    Analyzes fill events for execution quality assessment.

    Key metrics:
        - Fill rate: what % of the order got filled
        - Price improvement: did we get better than limit/worse than market
        - Fill time: how long did it take
        - Partial fills: were fills fragmented
    """

    def __init__(self) -> None:
        self._analyses: list[FillAnalysis] = []

    async def analyze(
        self,
        order_id: str,
        fills: list[dict],
        target_quantity: int,
        arrival_price: float,
        limit_price: Optional[float] = None,
        order_create_time: Optional[datetime] = None,
    ) -> FillAnalysis:
        """Analyze fill events for an order."""
        analysis = FillAnalysis(
            order_id=order_id,
            total_target=target_quantity,
            arrival_price=arrival_price,
            limit_price=limit_price,
        )

        if not fills:
            analysis.fill_rate = 0.0
            return analysis

        total_qty = sum(f.get("quantity", 0) for f in fills)
        analysis.total_filled = total_qty
        analysis.num_fills = len(fills)
        analysis.fill_rate = total_qty / max(target_quantity, 1)
        analysis.avg_fill_size = total_qty / max(len(fills), 1)

        # Average fill price
        total_notional = sum(f.get("quantity", 0) * f.get("price", 0) for f in fills)
        analysis.avg_fill_price = total_notional / max(total_qty, 1)

        # Price improvement vs arrival
        if arrival_price > 0 and analysis.avg_fill_price > 0:
            analysis.price_improvement_bps = (
                (arrival_price - analysis.avg_fill_price) / arrival_price * 10000
            )

        # Venue breakdown
        for fill in fills:
            venue = fill.get("venue", "UNKNOWN")
            analysis.venue_fills[venue] = analysis.venue_fills.get(venue, 0) + fill.get("quantity", 0)

        # Timing
        if order_create_time and fills:
            timestamps = [
                f.get("timestamp") for f in fills
                if f.get("timestamp") is not None
            ]
            if timestamps:
                first = min(timestamps)
                last = max(timestamps)
                analysis.time_to_first_fill_seconds = (
                    first - order_create_time
                ).total_seconds()
                analysis.time_to_completion_seconds = (
                    last - order_create_time
                ).total_seconds()

        self._analyses.append(analysis)
        if len(self._analyses) > 500:
            self._analyses = self._analyses[-250:]

        return analysis

    async def get_venue_stats(self) -> dict[str, dict]:
        """Get fill statistics by venue."""
        venue_data: dict[str, list[float]] = {}
        for analysis in self._analyses:
            for venue, qty in analysis.venue_fills.items():
                if venue not in venue_data:
                    venue_data[venue] = []
                venue_data[venue].append(analysis.fill_rate)

        stats = {}
        for venue, rates in venue_data.items():
            stats[venue] = {
                "avg_fill_rate": sum(rates) / len(rates),
                "sample_count": len(rates),
            }
        return stats
