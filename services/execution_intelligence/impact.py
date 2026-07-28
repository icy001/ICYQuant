"""Market Impact Model – estimate price impact of large orders."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .order import ExecutionOrder


@dataclass
class ImpactEstimate:
    """Estimated market impact for an order."""

    symbol: str
    impact_bps: float  # basis points
    temporary_impact_bps: float = 0.0  # reverts after execution
    permanent_impact_bps: float = 0.0  # permanent price change
    confidence: float = 0.5
    recommendation: str = ""  # "single", "split", "algorithmic"

    def total_bps(self) -> float:
        return round(self.temporary_impact_bps + self.permanent_impact_bps, 2)

    def is_high_impact(self, threshold_bps: float = 5.0) -> bool:
        return self.total_bps() >= threshold_bps

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "impact_bps": self.impact_bps,
            "temporary_impact_bps": self.temporary_impact_bps,
            "permanent_impact_bps": self.permanent_impact_bps,
            "total_bps": self.total_bps(),
            "confidence": self.confidence,
            "recommendation": self.recommendation,
            "is_high_impact": self.is_high_impact(),
        }


class MarketImpactModel:
    """Estimates the market impact of executing an order.

    Uses the Almgren-Chriss style model:
    - Temporary impact: decays after execution completes
    - Permanent impact: information leakage, persists in price

    Both are functions of order size, market volume, and volatility.
    """

    def __init__(
        self,
        eta: float = 0.1,  # temporary impact coefficient
        gamma: float = 0.05,  # permanent impact coefficient
        volatility: float = 0.20,  # annualized volatility
    ):
        self.eta = eta
        self.gamma = gamma
        self.volatility = volatility

    def estimate(self, quantity: int,
                 avg_daily_volume: int = 1_000_000,
                 price: float = 100.0) -> float:
        """Quick estimate of total market impact in basis points."""
        result = self.estimate_detailed(quantity, avg_daily_volume, price)
        return result.impact_bps

    def estimate_detailed(
        self,
        quantity: int,
        avg_daily_volume: int = 1_000_000,
        price: float = 100.0,
    ) -> ImpactEstimate:
        """Detailed market impact estimate with temporary/permanent split.

        Args:
            quantity: Order quantity in shares.
            avg_daily_volume: Average daily volume for the instrument.
            price: Current price per share.
        """
        if avg_daily_volume <= 0:
            avg_daily_volume = 1

        # Participation rate (what % of daily volume)
        participation = quantity / avg_daily_volume

        # Daily volatility in bps
        daily_vol_bps = (self.volatility / (252 ** 0.5)) * 10000

        # Temporary impact: proportional to participation and volatility
        temporary_bps = self.eta * participation * daily_vol_bps * 100

        # Permanent impact: information leakage, smaller but persistent
        permanent_bps = self.gamma * (participation ** 0.5) * daily_vol_bps * 100

        total_bps = round(temporary_bps + permanent_bps, 2)

        # Recommendation based on impact
        if total_bps < 2.0:
            rec = "single"  # execute as single order
        elif total_bps < 10.0:
            rec = "split"  # split into multiple slices
        else:
            rec = "algorithmic"  # use algorithmic execution (VWAP/TWAP)

        return ImpactEstimate(
            symbol="",
            impact_bps=total_bps,
            temporary_impact_bps=round(temporary_bps, 2),
            permanent_impact_bps=round(permanent_bps, 2),
            confidence=min(0.9, 0.4 + participation * 5.0),
            recommendation=rec,
        )

    def estimate_for_order(
        self,
        order: ExecutionOrder,
        avg_daily_volume: int = 1_000_000,
        price: float = 100.0,
    ) -> ImpactEstimate:
        """Estimate market impact for an ExecutionOrder."""
        result = self.estimate_detailed(order.quantity, avg_daily_volume, price)
        result.symbol = order.symbol
        return result

    def optimal_slice_count(
        self,
        quantity: int,
        avg_daily_volume: int = 1_000_000,
        price: float = 100.0,
        max_impact_per_slice_bps: float = 2.0,
    ) -> int:
        """Recommend optimal number of slices to keep per-slice impact low."""
        if quantity <= 0 or avg_daily_volume <= 0:
            return 1

        impact = self.estimate(quantity, avg_daily_volume, price)
        if impact <= max_impact_per_slice_bps:
            return 1

        # Estimate slices needed to bring per-slice impact below threshold
        slices = max(1, int(impact / max_impact_per_slice_bps))
        return min(slices, 50)  # cap at 50 slices

    def cost_savings(
        self,
        quantity: int,
        avg_daily_volume: int = 1_000_000,
        price: float = 100.0,
    ) -> dict:
        """Estimate cost savings from splitting vs single execution."""
        single_impact = self.estimate(quantity, avg_daily_volume, price)
        slices = self.optimal_slice_count(quantity, avg_daily_volume, price)
        per_slice_qty = quantity // slices
        per_slice_impact = self.estimate(per_slice_qty, avg_daily_volume, price)

        savings_bps = single_impact - per_slice_impact * slices / slices

        return {
            "single_impact_bps": single_impact,
            "slices_recommended": slices,
            "per_slice_impact_bps": per_slice_impact,
            "estimated_savings_bps": round(savings_bps, 2),
        }
