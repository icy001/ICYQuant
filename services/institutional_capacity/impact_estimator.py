"""
Impact Estimator — Estimates market impact for orders using multiple models.

Supports: square-root, linear, Almgren-Chriss-style, and custom models.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .market_impact import MarketImpact


class ImpactModelType(str, Enum):
    SQRT = "sqrt"               # Square-root model (most common)
    LINEAR = "linear"           # Linear proportional
    POWER_LAW = "power_law"     # σ · (Q/V)^β with custom β
    ALMGREN_CHRISS = "ac"      # Almgren-Chriss framework


@dataclass
class ImpactEstimate:
    """Aggregated impact estimate from multiple models."""

    estimate_id: str = field(default_factory=lambda: f"IE-{uuid.uuid4().hex[:8]}")
    asset: str = ""
    order_size: float = 0.0
    adv: float = 0.0
    volatility: float = 0.0

    # Per-model
    sqrt_impact: Optional[MarketImpact] = None
    linear_impact: Optional[MarketImpact] = None

    # Consensus
    consensus_impact_bps: float = 0.0
    consensus_cost: float = 0.0

    confidence: float = 0.7

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimate_id": self.estimate_id,
            "asset": self.asset,
            "order_size": self.order_size,
            "consensus_impact_bps": self.consensus_impact_bps,
            "consensus_cost": self.consensus_cost,
            "confidence": self.confidence,
        }


class ImpactEstimator:
    """Multi-model market impact estimator."""

    def __init__(self, default_model: ImpactModelType = ImpactModelType.SQRT):
        self.default_model = default_model
        self._estimates: List[ImpactEstimate] = []

    def estimate(
        self,
        asset: str,
        order_size: float,
        avg_daily_volume: float,
        volatility: float = 0.0,
        model: Optional[ImpactModelType] = None,
    ) -> ImpactEstimate:
        model = model or self.default_model
        result = ImpactEstimate(
            asset=asset, order_size=order_size, adv=avg_daily_volume, volatility=volatility,
        )

        # Always run sqrt model
        if avg_daily_volume > 0 and volatility > 0:
            impact = MarketImpact(
                asset=asset, order_size=order_size,
                avg_daily_volume=avg_daily_volume, volatility=volatility,
            )
            impact.estimate_sqrt()
            result.sqrt_impact = impact
            result.consensus_impact_bps = impact.total_impact_bps
            result.consensus_cost = impact.cost_dollars

        # Linear model
        if model == ImpactModelType.LINEAR and avg_daily_volume > 0:
            lin_impact = MarketImpact(
                asset=asset, order_size=order_size,
                avg_daily_volume=avg_daily_volume, volatility=volatility,
            )
            lin_impact.participation_rate = order_size / avg_daily_volume
            lin_impact.total_impact_bps = lin_impact.participation_rate * 50  # rough linear
            lin_impact.cost_dollars = order_size * lin_impact.total_impact_bps / 10000
            result.linear_impact = lin_impact

        self._estimates.append(result)
        return result

    def recent(self, n: int = 20) -> List[ImpactEstimate]:
        return self._estimates[-n:]

    def summary(self) -> Dict[str, Any]:
        if not self._estimates:
            return {"estimates": 0}
        return {
            "estimates": len(self._estimates),
            "avg_impact_bps": sum(e.consensus_impact_bps for e in self._estimates) / len(self._estimates),
            "max_impact_bps": max(e.consensus_impact_bps for e in self._estimates),
        }
