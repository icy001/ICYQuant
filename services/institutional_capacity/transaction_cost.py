"""
Transaction Cost — Unified total cost of trading.

Total Cost = Commission + Spread Cost + Slippage + Market Impact + Liquidity Cost.

Enables Portfolio Optimizer to compare: Expected Alpha vs Expected Trading Cost.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TransactionCost:
    """Complete per-trade cost breakdown."""

    cost_id: str = field(default_factory=lambda: f"TC-{uuid.uuid4().hex[:8]}")
    asset: str = ""
    order_size: float = 0.0

    # Components (all in bps)
    commission_bps: float = 0.0
    spread_cost_bps: float = 0.0
    slippage_bps: float = 0.0
    market_impact_bps: float = 0.0
    liquidity_cost_bps: float = 0.0

    # Totals
    total_cost_bps: float = 0.0
    total_cost_dollars: float = 0.0

    # Net
    expected_alpha_bps: float = 0.0
    net_alpha_bps: float = 0.0           # alpha - total_cost
    is_economical: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cost_id": self.cost_id,
            "asset": self.asset,
            "order_size": self.order_size,
            "commission_bps": self.commission_bps,
            "spread_cost_bps": self.spread_cost_bps,
            "slippage_bps": self.slippage_bps,
            "market_impact_bps": self.market_impact_bps,
            "liquidity_cost_bps": self.liquidity_cost_bps,
            "total_cost_bps": self.total_cost_bps,
            "total_cost_dollars": self.total_cost_dollars,
            "net_alpha_bps": self.net_alpha_bps,
            "is_economical": self.is_economical,
        }

    def compute_total(self) -> float:
        self.total_cost_bps = (
            self.commission_bps + self.spread_cost_bps + self.slippage_bps +
            self.market_impact_bps + self.liquidity_cost_bps
        )
        self.total_cost_dollars = self.order_size * self.total_cost_bps / 10000
        self.net_alpha_bps = self.expected_alpha_bps - self.total_cost_bps
        self.is_economical = self.net_alpha_bps > 0
        return self.total_cost_bps


class TransactionCostModel:
    """Unified transaction cost model."""

    def __init__(self, commission_bps: float = 1.0):
        self.commission_bps = commission_bps

    def estimate(
        self, asset: str, order_size: float,
        spread_bps: float = 0.0, slippage_bps: float = 0.0,
        impact_bps: float = 0.0, liquidity_cost_bps: float = 0.0,
        expected_alpha_bps: float = 0.0,
    ) -> TransactionCost:
        cost = TransactionCost(
            asset=asset, order_size=order_size,
            commission_bps=self.commission_bps,
            spread_cost_bps=spread_bps * 0.5,
            slippage_bps=slippage_bps,
            market_impact_bps=impact_bps,
            liquidity_cost_bps=liquidity_cost_bps,
            expected_alpha_bps=expected_alpha_bps,
        )
        cost.compute_total()
        return cost

    def is_worth_trading(self, expected_alpha_bps: float, total_cost_bps: float, min_net: float = 2.0) -> bool:
        return expected_alpha_bps - total_cost_bps >= min_net
