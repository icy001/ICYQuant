"""
Liquidity Cost — Cost of trading in illiquid conditions.

Two strategies with similar alpha may have dramatically different liquidity costs.
Strategy A: Alpha 10%, Cost 1% → Net 9%. Strategy B: Alpha 11%, Cost 5% → Net 6%.
The optimizer must account for this to allocate capital wisely.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LiquidityCostEstimate:
    """Liquidity-driven cost estimate for a trade."""

    estimate_id: str = field(default_factory=lambda: f"LC-{uuid.uuid4().hex[:8]}")
    asset: str = ""

    # Liquidity metrics
    liquidity_score: float = 50.0
    liquidity_tier: str = "MID"

    # Cost components
    spread_impact_bps: float = 0.0
    depth_exhaustion_bps: float = 0.0
    adverse_selection_bps: float = 0.0

    # Total
    total_liquidity_cost_bps: float = 0.0
    total_liquidity_cost_dollars: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimate_id": self.estimate_id,
            "asset": self.asset,
            "liquidity_score": self.liquidity_score,
            "liquidity_tier": self.liquidity_tier,
            "total_liquidity_cost_bps": self.total_liquidity_cost_bps,
        }


class LiquidityCostModel:
    """Models liquidity-driven trading costs."""

    # Base cost by tier (bps)
    TIER_BASE_COST: Dict[str, float] = {
        "LARGE": 1.0, "MID": 3.0, "SMALL": 8.0, "ILLIQUID": 20.0,
    }

    def estimate(self, asset: str, liquidity_score: float, liquidity_tier: str = "MID",
                 order_size: float = 0.0, avg_daily_volume: float = 0.0) -> LiquidityCostEstimate:
        est = LiquidityCostEstimate(asset=asset, liquidity_score=liquidity_score, liquidity_tier=liquidity_tier)

        # Base cost from tier
        base = self.TIER_BASE_COST.get(liquidity_tier, 5.0)

        # Adjust for score
        score_factor = max(0.3, (100 - liquidity_score) / 50)

        est.spread_impact_bps = base * score_factor * 0.5
        est.depth_exhaustion_bps = base * score_factor * 0.3
        est.adverse_selection_bps = base * score_factor * 0.2

        # Extra for large participation
        if avg_daily_volume > 0 and order_size > 0:
            participation = order_size / avg_daily_volume
            if participation > 0.05:
                est.depth_exhaustion_bps += participation * 50

        est.total_liquidity_cost_bps = est.spread_impact_bps + est.depth_exhaustion_bps + est.adverse_selection_bps
        est.total_liquidity_cost_dollars = order_size * est.total_liquidity_cost_bps / 10000

        return est
