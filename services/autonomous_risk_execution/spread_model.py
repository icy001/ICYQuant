"""
Spread Model — bid-ask spread modeling and cost estimation.

Spreads drive a significant portion of execution cost:
    - Half-spread is the minimum cost of a round-trip trade
    - Spreads widen during volatility and news events
    - Spreads vary by asset, time of day, and market regime
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class SpreadProfile:
    """Spread characteristics for an asset."""
    asset: str = ""
    avg_spread_bps: float = 5.0
    current_spread_bps: float = 5.0
    min_spread_bps: float = 1.0
    max_spread_bps: float = 50.0
    spread_percentile: float = 0.5
    is_wide: bool = False
    regime: str = "NORMAL"


@dataclass
class SpreadCost:
    """Spread cost estimate."""
    half_spread_bps: float = 0.0
    expected_crossing_cost_bps: float = 0.0


class SpreadModel:
    """
    Bid-ask spread modeling.

    Key relationships:
        - Spread ∝ volatility (higher vol → wider spreads)
        - Spread ∝ 1/liquidity (less liquid → wider spreads)
        - Spread widens near market open/close
        - Spread spikes during news/events
    """

    def __init__(self) -> None:
        self._spread_data: dict[str, list[float]] = {}

    async def get_current_spread(
        self, asset: str, bid: float, ask: float, price: float,
    ) -> SpreadProfile:
        """Compute current spread characteristics."""
        if price <= 0:
            return SpreadProfile(asset=asset)

        spread = (ask - bid) / price * 10000  # bps
        profile = SpreadProfile(
            asset=asset,
            avg_spread_bps=spread,
            current_spread_bps=spread,
            is_wide=spread > 20,
        )

        # Track spread history
        if asset not in self._spread_data:
            self._spread_data[asset] = []
        self._spread_data[asset].append(spread)
        if len(self._spread_data[asset]) > 1000:
            self._spread_data[asset] = self._spread_data[asset][-500:]

        # Compute percentile
        history = self._spread_data[asset]
        if history:
            profile.min_spread_bps = min(history)
            profile.max_spread_bps = max(history)
            profile.avg_spread_bps = sum(history) / len(history)
            rank = sum(1 for s in history if s <= spread)
            profile.spread_percentile = rank / len(history)

        return profile

    async def estimate_cost(
        self, quantity: int, spread_bps: float, price: float = 100.0,
    ) -> SpreadCost:
        """Estimate spread crossing cost."""
        half_spread = spread_bps * 0.5

        # Crossing cost: half-spread for aggressive order
        # Additional cost for large size (wider execution)
        return SpreadCost(
            half_spread_bps=half_spread,
            expected_crossing_cost_bps=half_spread * 1.1,
        )

    def is_favorable(self, spread_bps: float) -> bool:
        """Check if spread is favorable for execution."""
        return spread_bps < 10

    def get_spread_history(self, asset: str) -> list[float]:
        """Get spread history for an asset."""
        return self._spread_data.get(asset, [])
