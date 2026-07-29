from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ImpactEstimate:
    symbol: str
    order_size: int
    avg_daily_volume: int
    participation_rate: float
    temporary_impact_bps: float = 0.0
    permanent_impact_bps: float = 0.0
    total_impact_bps: float = 0.0
    confidence_interval: tuple = (0.0, 0.0)
    factors: Dict[str, float] = field(default_factory=dict)


class MarketImpactPredictor:
    """Market Impact Prediction Engine - predicts the market impact of large orders."""

    def __init__(self):
        self.impact_coefficient = 0.1  # Almgren-Chriss style coefficient
        self.volatility_scaling = 1.0

    def predict(self, order):
        """Predict market impact for an order.

        Args:
            order: Order to analyze - can be ImpactEstimate dataclass or dict/symbol.

        Returns:
            Dict containing impact prediction.
        """
        if isinstance(order, ImpactEstimate):
            return self._predict_impact(order)
        return {"impact": order}

    def _predict_impact(self, order: ImpactEstimate) -> dict:
        if order.avg_daily_volume == 0:
            temporary = 0.0
            permanent = 0.0
        else:
            participation = order.order_size / order.avg_daily_volume
            temporary = self.impact_coefficient * (participation ** 0.5) * self.volatility_scaling * 10000
            permanent = temporary * 0.5  # Permanent impact is typically ~50% of temporary

        total = temporary + permanent

        return {
            "impact": {
                "symbol": order.symbol,
                "order_size": order.order_size,
                "avg_daily_volume": order.avg_daily_volume,
                "participation_rate": round(participation, 4),
                "temporary_impact_bps": round(temporary, 2),
                "permanent_impact_bps": round(permanent, 2),
                "total_impact_bps": round(total, 2),
                "severity": self._classify_impact(total),
            }
        }

    def _classify_impact(self, total_bps: float) -> str:
        if total_bps < 2:
            return "LOW"
        elif total_bps < 5:
            return "MEDIUM"
        elif total_bps < 10:
            return "HIGH"
        return "CRITICAL"

    def calculate_optimal_participation(self, urgency: str, impact_tolerance_bps: float) -> float:
        """Calculate optimal participation rate given urgency and impact tolerance."""
        base_rate = {
            "LOW": 0.02,
            "NORMAL": 0.05,
            "HIGH": 0.10,
        }.get(urgency, 0.05)

        if impact_tolerance_bps < 3:
            return base_rate * 0.5
        elif impact_tolerance_bps > 10:
            return base_rate * 2.0
        return base_rate
