"""
Fill Probability Model — estimates probability of order execution.

Answers: "If I place a limit order at price X, what's the probability
         it gets filled within time T?"

Trade-off:
    Better price → lower fill probability
    Worse price → higher fill probability, more cost
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class FillProbabilityEstimate:
    """Fill probability estimation."""
    id: str = field(default_factory=lambda: str(uuid4()))
    asset: str = ""
    limit_price: float = 0.0
    mid_price: float = 0.0
    offset_bps: float = 0.0  # How far from mid
    probability: float = 0.50
    expected_fill_time_seconds: float = 60.0
    is_aggressive: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


class FillProbability:
    """
    Estimates fill probability for limit orders.

    Model: Fill probability decays exponentially with distance from mid.
        P(fill) = exp(-λ * |offset|)

    Where:
        λ = calibration parameter (higher = faster decay)
        offset = distance from mid-price in bps

    Guidelines:
        - At mid/better: ~50-60% probability
        - 2 bps away: ~35-45%
        - 5 bps away: ~15-25%
        - 10+ bps away: <10%
    """

    def __init__(self, lambda_param: float = 0.15) -> None:
        self._lambda = lambda_param
        self._history: list[dict] = []

    async def estimate(
        self,
        limit_price: float,
        mid_price: float,
        side: str = "BUY",
        spread_bps: float = 5.0,
        volatility: float = 0.15,
        time_horizon_seconds: int = 60,
    ) -> FillProbabilityEstimate:
        """Estimate fill probability for a limit order."""
        if mid_price <= 0:
            return FillProbabilityEstimate()

        # Offset from mid (positive = aggressive, negative = passive)
        if side.upper() == "BUY":
            offset = (limit_price - mid_price) / mid_price * 10000
        else:
            offset = (mid_price - limit_price) / mid_price * 10000

        # Base probability decays with distance
        distance = max(0, -offset)  # How far from favorable side
        base_prob = math.exp(-self._lambda * distance)

        # Adjust for volatility (higher vol = more crosses = higher fill prob)
        vol_factor = 1.0 + (volatility - 0.15) * 2

        # Adjust for time (longer horizon = higher fill prob)
        time_factor = min(1.0 + math.log(max(time_horizon_seconds, 1) / 60) * 0.15, 2.0)

        # Adjust for spread (wider spread = easier to fill at mid)
        spread_factor = 1.0 + (spread_bps / 20) * 0.2

        probability = min(0.99, base_prob * vol_factor * time_factor * spread_factor)
        probability = max(0.01, probability)

        # Expected fill time
        if probability > 0.01:
            expected_time = -math.log(1 - probability) / (self._lambda * vol_factor)
        else:
            expected_time = float("inf")

        return FillProbabilityEstimate(
            limit_price=limit_price,
            mid_price=mid_price,
            offset_bps=offset,
            probability=probability,
            expected_fill_time_seconds=expected_time,
            is_aggressive=offset >= 0,
        )

    async def find_optimal_price(
        self,
        mid_price: float,
        side: str,
        target_probability: float = 0.70,
        spread_bps: float = 5.0,
        volatility: float = 0.15,
    ) -> float:
        """
        Find the optimal limit price for a target fill probability.

        Balances: better price vs higher fill probability.
        """
        # Search for price that gives target probability
        lo, hi = -20, 20  # bps search range
        best_price = mid_price

        for _ in range(20):
            offset = (lo + hi) / 2
            test_price = mid_price * (1 + offset / 10000 * (1 if side == "BUY" else -1))
            est = await self.estimate(
                test_price, mid_price, side, spread_bps, volatility,
            )
            if est.probability > target_probability:
                hi = offset
                best_price = test_price
            else:
                lo = offset

        return best_price

    def calibrate(self, fill_data: list[dict]) -> None:
        """Calibrate lambda parameter from historical fill data."""
        self._history = fill_data
        if not fill_data:
            return
        # Simplified calibration
        avg_distance = sum(
            abs(d.get("offset_bps", 5)) for d in fill_data
        ) / len(fill_data)
        avg_fill = sum(
            d.get("filled", 0) for d in fill_data
        ) / len(fill_data)
        if avg_distance > 0 and avg_fill > 0:
            self._lambda = -math.log(max(avg_fill, 0.01)) / max(avg_distance, 0.01)
