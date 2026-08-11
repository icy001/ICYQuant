"""
Slippage Model — Expected slippage from spread, volatility, liquidity, participation.

Expected Execution Price ≠ Market Price at decision time.
Slippage = f(spread, volatility, liquidity, participation, order_size, execution_window).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SlippageEstimate:
    """Expected slippage for an order execution."""

    estimate_id: str = field(default_factory=lambda: f"SE-{uuid.uuid4().hex[:8]}")
    asset: str = ""

    # Inputs
    order_size: float = 0.0
    market_price: float = 0.0
    spread_bps: float = 0.0
    volatility: float = 0.0
    interval_volume: float = 0.0

    # Components
    half_spread_cost_bps: float = 0.0        # crossing the spread
    volatility_slippage_bps: float = 0.0      # price movement during execution
    liquidity_slippage_bps: float = 0.0       # market impact

    total_slippage_bps: float = 0.0
    total_slippage_dollars: float = 0.0

    expected_execution_price: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimate_id": self.estimate_id,
            "asset": self.asset,
            "half_spread_cost_bps": self.half_spread_cost_bps,
            "volatility_slippage_bps": self.volatility_slippage_bps,
            "liquidity_slippage_bps": self.liquidity_slippage_bps,
            "total_slippage_bps": self.total_slippage_bps,
            "expected_execution_price": self.expected_execution_price,
        }


class SlippageModel:
    """Estimates execution slippage for orders."""

    def estimate(
        self, asset: str, order_size: float, market_price: float,
        spread_bps: float = 0.0, volatility: float = 0.0,
        interval_volume: float = 0.0, side: str = "BUY",
    ) -> SlippageEstimate:
        est = SlippageEstimate(
            asset=asset, order_size=order_size, market_price=market_price,
            spread_bps=spread_bps, volatility=volatility, interval_volume=interval_volume,
        )

        # Half-spread cost (always paid when crossing spread)
        est.half_spread_cost_bps = spread_bps * 0.5

        # Volatility slippage: expected adverse movement during execution
        if volatility > 0 and interval_volume > 0:
            participation = order_size / interval_volume
            est.volatility_slippage_bps = volatility * participation * 10000

        # Liquidity slippage: market impact component
        if interval_volume > 0:
            part = order_size / interval_volume
            est.liquidity_slippage_bps = volatility * (part ** 0.5) * 10000 * 0.5

        est.total_slippage_bps = est.half_spread_cost_bps + est.volatility_slippage_bps + est.liquidity_slippage_bps
        est.total_slippage_dollars = order_size * est.total_slippage_bps / 10000

        # Expected execution price
        sign = -1 if side == "BUY" else 1
        est.expected_execution_price = market_price * (1 + sign * est.total_slippage_bps / 10000)

        return est
