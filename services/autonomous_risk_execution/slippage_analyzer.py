"""
Slippage Analyzer — measures realized vs expected slippage.

Compares:
    - Arrival price vs execution price
    - Decision price vs execution price
    - Expected slippage vs realized slippage
    - Strategy-specific slippage patterns
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class SlippageMeasurement:
    """Single slippage measurement."""
    order_id: str = ""
    asset: str = ""

    # Prices
    decision_price: float = 0.0
    arrival_price: float = 0.0
    execution_price: float = 0.0

    # Realized
    decision_to_arrival_bps: float = 0.0
    arrival_to_execution_bps: float = 0.0
    total_slippage_bps: float = 0.0

    # Expected
    expected_slippage_bps: float = 0.0
    slippage_error_bps: float = 0.0

    strategy: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SlippageStats:
    """Aggregate slippage statistics."""
    count: int = 0
    avg_slippage_bps: float = 0.0
    avg_expected_bps: float = 0.0
    avg_error_bps: float = 0.0
    max_slippage_bps: float = 0.0
    pct_within_expected: float = 0.0
    by_strategy: dict[str, dict] = field(default_factory=dict)


class SlippageAnalyzer:
    """
    Analyzes realized slippage vs expectations.

    Key questions:
        - Are we consistently over/under-estimating slippage?
        - Which strategies have the best/worst slippage?
        - Is slippage improving or degrading over time?
    """

    def __init__(self) -> None:
        self._measurements: list[SlippageMeasurement] = []
        self._total_analyzed: int = 0

    async def measure(
        self,
        order_id: str,
        asset: str,
        decision_price: float,
        arrival_price: float,
        execution_price: float,
        expected_slippage_bps: float = 0.0,
        strategy: str = "",
    ) -> SlippageMeasurement:
        """Measure realized slippage for an order."""
        measurement = SlippageMeasurement(
            order_id=order_id,
            asset=asset,
            decision_price=decision_price,
            arrival_price=arrival_price,
            execution_price=execution_price,
            expected_slippage_bps=expected_slippage_bps,
            strategy=strategy,
        )

        if arrival_price > 0:
            measurement.arrival_to_execution_bps = (
                (execution_price - arrival_price) / arrival_price * 10000
            )

        if decision_price > 0:
            measurement.decision_to_arrival_bps = (
                (arrival_price - decision_price) / decision_price * 10000
            )
            measurement.total_slippage_bps = (
                (execution_price - decision_price) / decision_price * 10000
            )

        measurement.slippage_error_bps = (
            abs(measurement.total_slippage_bps) - expected_slippage_bps
        )

        self._measurements.append(measurement)
        self._total_analyzed += 1
        if len(self._measurements) > 1000:
            self._measurements = self._measurements[-500:]

        return measurement

    async def get_stats(self) -> SlippageStats:
        """Get aggregate slippage statistics."""
        if not self._measurements:
            return SlippageStats()

        stats = SlippageStats(count=len(self._measurements))
        slippages = [m.total_slippage_bps for m in self._measurements]
        errors = [m.slippage_error_bps for m in self._measurements]

        stats.avg_slippage_bps = sum(slippages) / len(slippages)
        stats.avg_expected_bps = sum(m.expected_slippage_bps for m in self._measurements) / len(self._measurements)
        stats.avg_error_bps = sum(errors) / len(errors)
        stats.max_slippage_bps = max(slippages, key=abs)

        # Within expected
        within = sum(1 for m in self._measurements
                     if abs(m.total_slippage_bps) <= m.expected_slippage_bps * 1.5)
        stats.pct_within_expected = within / len(self._measurements)

        # By strategy
        strategies = {}
        for m in self._measurements:
            s = m.strategy or "UNKNOWN"
            if s not in strategies:
                strategies[s] = {"count": 0, "total_slippage": 0.0}
            strategies[s]["count"] += 1
            strategies[s]["total_slippage"] += abs(m.total_slippage_bps)

        for s, data in strategies.items():
            data["avg_slippage_bps"] = data["total_slippage"] / max(data["count"], 1)

        stats.by_strategy = strategies
        return stats
