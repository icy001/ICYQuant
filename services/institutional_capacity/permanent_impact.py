"""
Permanent Impact — Lasting price shift from large order flow.

Large orders convey information → market reprices → new equilibrium.
This impact does NOT reverse after the order completes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PermanentImpact:
    """Permanent (information-based) market impact."""

    impact_id: str = field(default_factory=lambda: f"PI-{uuid.uuid4().hex[:8]}")
    asset: str = ""
    order_size: float = 0.0
    avg_daily_volume: float = 0.0
    volatility: float = 0.0

    # Model
    daily_participation: float = 0.0      # order / ADV
    estimated_impact_bps: float = 0.0
    information_ratio: float = 0.0        # how much is information vs liquidity

    # Cost (permanent — not recovered)
    permanent_cost_bps: float = 0.0
    permanent_cost_dollars: float = 0.0

    # Signal
    signal_strength: float = 0.0          # 0 = pure liquidity, 1 = strong information
    adverse_selection_cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "impact_id": self.impact_id,
            "asset": self.asset,
            "daily_participation": self.daily_participation,
            "estimated_impact_bps": self.estimated_impact_bps,
            "permanent_cost_dollars": self.permanent_cost_dollars,
        }

    def estimate(self, scale: float = 1.0) -> "PermanentImpact":
        """Permanent impact: σ * scale * (Q/ADV)^0.5 * 0.4"""
        if self.avg_daily_volume <= 0:
            return self

        self.daily_participation = self.order_size / self.avg_daily_volume
        self.estimated_impact_bps = self.volatility * scale * (self.daily_participation ** 0.5) * 10000 * 0.4
        self.permanent_cost_bps = self.estimated_impact_bps
        self.permanent_cost_dollars = self.order_size * self.estimated_impact_bps / 10000

        return self
