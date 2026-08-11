"""
Spread Model — Bid-ask spread modeling and cost estimation.

Models effective spread, realized spread, and spread as function of
order size and market conditions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SpreadEstimate:
    """Bid-ask spread cost estimate."""

    estimate_id: str = field(default_factory=lambda: f"SE-{uuid.uuid4().hex[:8]}")
    asset: str = ""

    quoted_spread_bps: float = 0.0
    effective_spread_bps: float = 0.0       # actual execution spread
    realized_spread_bps: float = 0.0         # post-trade price reversal

    half_spread_cost_bps: float = 0.0        # one-way crossing cost
    spread_cost_dollars: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimate_id": self.estimate_id,
            "asset": self.asset,
            "quoted_spread_bps": self.quoted_spread_bps,
            "effective_spread_bps": self.effective_spread_bps,
            "half_spread_cost_bps": self.half_spread_cost_bps,
            "spread_cost_dollars": self.spread_cost_dollars,
        }


class SpreadModel:
    """Models bid-ask spread costs."""

    def estimate(self, asset: str, quoted_spread_bps: float, order_size: float = 0.0,
                 book_depth_at_best: float = 0.0) -> SpreadEstimate:
        est = SpreadEstimate(
            asset=asset,
            quoted_spread_bps=quoted_spread_bps,
        )

        # Basic: effective spread ≈ quoted spread for small orders
        est.effective_spread_bps = quoted_spread_bps

        # If order exceeds depth at best, effective spread widens
        if book_depth_at_best > 0 and order_size > book_depth_at_best:
            excess = order_size / max(book_depth_at_best, 1)
            est.effective_spread_bps = quoted_spread_bps * (1 + excess * 0.3)

        # One-way cost: half the effective spread
        est.half_spread_cost_bps = est.effective_spread_bps * 0.5
        est.spread_cost_dollars = order_size * est.half_spread_cost_bps / 10000

        return est
