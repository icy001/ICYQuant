"""
Impact Curve — Maps order size to expected market impact.

Non-linear: 1M→2bps, 5M→5bps, 10M→11bps, 20M→27bps, 50M→71bps

Used by Portfolio Orchestrator to compare expected alpha vs expected cost.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ImpactPoint:
    """A single point on the impact curve."""
    order_size: float
    impact_bps: float
    marginal_impact_bps_per_m: float = 0.0


@dataclass
class ImpactCurve:
    """Full impact curve for an asset."""

    curve_id: str = field(default_factory=lambda: f"IC-{uuid.uuid4().hex[:8]}")
    asset: str = ""
    avg_daily_volume: float = 0.0
    volatility: float = 0.0

    points: List[ImpactPoint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "curve_id": self.curve_id,
            "asset": self.asset,
            "adv": self.avg_daily_volume,
            "points": [{"size": p.order_size, "impact_bps": p.impact_bps} for p in self.points],
        }

    def build(self, max_participation: float = 0.20, steps: int = 20) -> "ImpactCurve":
        """Build impact curve using square-root model."""
        import math
        self.points = []
        for i in range(steps + 1):
            part = max_participation * i / steps
            size = self.avg_daily_volume * part
            impact = self.volatility * (part ** 0.5) * 10000 if part > 0 else 0
            self.points.append(ImpactPoint(order_size=size, impact_bps=impact))
        return self

    def impact_at(self, order_size: float) -> float:
        """Get impact estimate for a given order size."""
        if not self.points or order_size <= 0:
            return 0.0
        for i, p in enumerate(self.points):
            if p.order_size >= order_size:
                if i == 0:
                    return p.impact_bps
                prev = self.points[i - 1]
                ratio = (order_size - prev.order_size) / max(p.order_size - prev.order_size, 1)
                return prev.impact_bps + ratio * (p.impact_bps - prev.impact_bps)
        return self.points[-1].impact_bps

    def max_order_at_impact(self, max_impact_bps: float) -> float:
        """Maximum order size for a given impact budget."""
        for p in self.points:
            if p.impact_bps > max_impact_bps:
                return p.order_size
        return self.points[-1].order_size if self.points else 0.0
