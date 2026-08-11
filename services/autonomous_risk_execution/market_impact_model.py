"""
Market Impact Model — estimates price impact of trading.

Models used:
    - Square-root model (Almgren-Chriss style):
        Impact = σ * (Q / ADV)^γ

    - Linear model:
        Impact = η * Q / ADV

    - Power-law model:
        Impact = α * (Q / ADV)^β * σ

Default: Square-root with γ=0.5, calibrated per asset.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ImpactParams:
    """Market impact model parameters."""
    asset: str = ""
    eta: float = 0.1  # Linear impact coefficient
    gamma: float = 0.5  # Non-linear exponent (0.5 = square root)
    sigma: float = 0.02  # Daily volatility
    permanent_impact_ratio: float = 0.3  # How much impact is permanent
    decay_half_life_minutes: float = 30  # How fast temporary impact decays


@dataclass
class ImpactEstimate:
    """Market impact estimation."""
    id: str = field(default_factory=lambda: str(uuid4()))
    asset: str = ""
    temporary_impact_bps: float = 0.0
    permanent_impact_bps: float = 0.0
    total_impact_bps: float = 0.0
    impact_cost: float = 0.0  # In notional terms
    pct_adv: float = 0.0
    model: str = "square_root"
    timestamp: datetime = field(default_factory=datetime.now)


class MarketImpactModel:
    """
    Estimates market impact of order execution.

    Square-root model (primary):
        Impact = σ * sqrt(Q / ADV) * 100  [in bps]

    Where:
        σ = daily volatility
        Q = order quantity
        ADV = average daily volume

    This model captures the empirical observation that
    impact grows with the square root of trade size.
    """

    def __init__(self) -> None:
        self._asset_params: dict[str, ImpactParams] = {}
        self._last_estimates: list[ImpactEstimate] = []

    async def estimate(
        self,
        asset: str,
        quantity: int,
        adv: float,
        volatility: float = 0.02,
        participation: float = 0.10,
        model: str = "square_root",
    ) -> ImpactEstimate:
        """Estimate market impact in bps."""
        pct_adv = abs(quantity) / max(adv, 1)
        params = self._asset_params.get(asset, ImpactParams(
            asset=asset, sigma=volatility,
        ))

        if model == "square_root":
            total = params.sigma * (pct_adv ** params.gamma) * 100
        elif model == "linear":
            total = params.eta * pct_adv * 100
        else:  # power_law
            total = params.eta * (pct_adv ** params.gamma) * params.sigma * 100

        # Split into temporary and permanent
        temporary = total * (1 - params.permanent_impact_ratio)
        permanent = total * params.permanent_impact_ratio

        impact_cost = pct_adv * total / 10000  # Notional cost ratio

        estimate = ImpactEstimate(
            asset=asset,
            temporary_impact_bps=temporary,
            permanent_impact_bps=permanent,
            total_impact_bps=total,
            impact_cost=impact_cost,
            pct_adv=pct_adv,
            model=model,
        )
        self._last_estimates.append(estimate)
        if len(self._last_estimates) > 500:
            self._last_estimates = self._last_estimates[-250:]

        return estimate

    async def estimate_multi(
        self, orders: list[dict]
    ) -> dict[str, ImpactEstimate]:
        """Estimate impact for multiple orders simultaneously."""
        results = {}
        for order in orders:
            est = await self.estimate(
                order.get("asset", ""),
                order.get("quantity", 0),
                order.get("adv", 1_000_000),
                order.get("volatility", 0.02),
            )
            results[est.asset] = est
        return results

    def calibrate(
        self, asset: str, historical_trades: list[dict]
    ) -> ImpactParams:
        """Calibrate impact parameters from historical data."""
        params = ImpactParams(asset=asset)
        # Simplified calibration
        if historical_trades:
            avg_impact = sum(t.get("impact_bps", 0) for t in historical_trades) / len(historical_trades)
            avg_pct = sum(t.get("pct_adv", 0) for t in historical_trades) / len(historical_trades)
            if avg_pct > 0:
                params.eta = avg_impact / (avg_pct * 100)
        self._asset_params[asset] = params
        return params
