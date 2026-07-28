"""Slippage Predictor – forecast expected execution slippage."""

from dataclasses import dataclass
from typing import Optional

from .order import ExecutionOrder


@dataclass
class SlippageEstimate:
    """A slippage prediction with confidence and contributing factors."""

    symbol: str
    estimated_bps: float  # basis points (0.01% = 1 bps)
    confidence: float = 0.5  # 0-1
    factors: dict = None

    def __post_init__(self):
        if self.factors is None:
            self.factors = {}

    def is_significant(self, threshold_bps: float = 1.0) -> bool:
        return abs(self.estimated_bps) >= threshold_bps

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "estimated_bps": self.estimated_bps,
            "confidence": self.confidence,
            "factors": self.factors,
            "is_significant": self.is_significant(),
        }


class SlippagePredictor:
    """Predicts execution slippage based on order characteristics.

    Factors considered:
    - Order size relative to market volume
    - Order urgency (higher urgency = more slippage)
    - Bid-ask spread estimate
    - Market volatility
    - Side (buy slippage vs sell slippage)
    """

    def __init__(
        self,
        base_spread_bps: float = 1.0,
        volatility_bps: float = 0.5,
    ):
        self.base_spread_bps = base_spread_bps
        self.volatility_bps = volatility_bps

    def predict(self, order: ExecutionOrder,
                market_volume: int = 100_000,
                spread_bps: Optional[float] = None) -> float:
        """Predict slippage in basis points for the given order.

        Returns a positive number (always adverse for the trader):
        - BUY: expected to pay above mid
        - SELL: expected to receive below mid
        """
        estimate = self.predict_detailed(order, market_volume, spread_bps)
        return estimate.estimated_bps

    def predict_detailed(
        self,
        order: ExecutionOrder,
        market_volume: int = 100_000,
        spread_bps: Optional[float] = None,
    ) -> SlippageEstimate:
        """Predict slippage with detailed factor breakdown."""

        s = spread_bps if spread_bps is not None else self.base_spread_bps

        # 1. Spread cost: half-spread (crossing the spread)
        spread_cost = s / 2.0

        # 2. Volume impact: larger % of market volume → more slippage
        participation = order.quantity / max(market_volume, 1)
        volume_impact = participation * 50.0  # scaled to bps

        # 3. Urgency multiplier
        urgency_mult = {
            "low": 0.5,
            "normal": 1.0,
            "high": 1.5,
            "critical": 2.5,
        }.get(order.urgency, 1.0)

        # 4. Volatility adjustment
        vol_impact = self.volatility_bps * urgency_mult

        # 5. Side adjustment (buy typically slightly worse)
        side_adj = 1.05 if order.side.upper() == "BUY" else 0.95

        total_bps = (spread_cost + volume_impact + vol_impact) * side_adj
        total_bps = round(max(total_bps, 0.0), 2)

        return SlippageEstimate(
            symbol=order.symbol,
            estimated_bps=total_bps,
            confidence=min(0.95, 0.5 + participation * 2.0),
            factors={
                "spread_cost_bps": round(spread_cost, 2),
                "volume_impact_bps": round(volume_impact, 2),
                "volatility_impact_bps": round(vol_impact, 2),
                "urgency_multiplier": urgency_mult,
                "side_adjustment": side_adj,
                "participation_rate": round(participation, 4),
            },
        )

    def expected_fill_price(
        self,
        order: ExecutionOrder,
        mid_price: float,
        market_volume: int = 100_000,
    ) -> float:
        """Compute the expected fill price given current mid."""
        slippage_bps = self.predict(order, market_volume)
        slippage_ratio = slippage_bps / 10000.0

        if order.side.upper() == "BUY":
            return round(mid_price * (1.0 + slippage_ratio), 4)
        else:
            return round(mid_price * (1.0 - slippage_ratio), 4)
