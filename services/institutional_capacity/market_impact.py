"""
Market Impact — Models the price impact of trading.

Distinguishes: Temporary Impact (during execution, partially recovers)
            and Permanent Impact (shifts equilibrium price).

Impact is typically non-linear: Impact ∝ σ · (Q/V)^β
where β ≈ 0.5 (square-root model).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MarketImpact:
    """Estimated market impact for an order."""

    impact_id: str = field(default_factory=lambda: f"MI-{uuid.uuid4().hex[:8]}")
    asset: str = ""

    order_size: float = 0.0                  # order notional
    avg_daily_volume: float = 0.0            # ADV notional
    volatility: float = 0.0                  # annualized

    # Model parameters
    participation_rate: float = 0.0          # Q / ADV
    impact_exponent: float = 0.5             # square-root model

    # Estimates
    total_impact_bps: float = 0.0
    temporary_impact_bps: float = 0.0
    permanent_impact_bps: float = 0.0

    cost_dollars: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "impact_id": self.impact_id,
            "asset": self.asset,
            "participation_rate": self.participation_rate,
            "total_impact_bps": self.total_impact_bps,
            "temporary_impact_bps": self.temporary_impact_bps,
            "permanent_impact_bps": self.permanent_impact_bps,
            "cost_dollars": self.cost_dollars,
        }

    def estimate_sqrt(self, scale_factor: float = 1.0) -> "MarketImpact":
        """Square-root impact model: Impact = σ * scale_factor * (Q/V)^β"""
        if self.avg_daily_volume <= 0:
            return self

        self.participation_rate = self.order_size / self.avg_daily_volume
        impact_pct = self.volatility * scale_factor * (self.participation_rate ** self.impact_exponent)
        self.total_impact_bps = impact_pct * 10000

        # 60% temporary, 40% permanent (typical split)
        self.temporary_impact_bps = self.total_impact_bps * 0.6
        self.permanent_impact_bps = self.total_impact_bps * 0.4

        self.cost_dollars = self.order_size * impact_pct
        return self
