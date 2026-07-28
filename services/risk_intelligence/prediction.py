"""Risk Prediction Engine – AI-driven forward risk forecasting."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RiskPrediction:
    """A forward-looking risk prediction.

    Projects key risk metrics over a given forecast horizon using
    market state signals and historical patterns.
    """

    current_volatility: float
    predicted_volatility: float
    forecast_horizon_days: int = 5
    confidence: float = 0.0  # 0-1
    trend: str = "stable"  # "increasing", "decreasing", "stable"
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "current_volatility": self.current_volatility,
            "predicted_volatility": self.predicted_volatility,
            "forecast_horizon_days": self.forecast_horizon_days,
            "confidence": self.confidence,
            "trend": self.trend,
            "warnings": self.warnings,
        }


class RiskPredictionEngine:
    """Forecasts future risk levels using market state indicators.

    Uses volatility momentum, correlation regime, and market stress
    signals to project risk metrics forward by a configurable horizon.
    """

    def __init__(
        self,
        default_horizon_days: int = 5,
        volatility_threshold: float = 0.3,
    ):
        self.default_horizon_days = default_horizon_days
        self.volatility_threshold = volatility_threshold

    def predict(
        self,
        current_volatility: float,
        vol_momentum: float = 0.0,
        correlation_regime: float = 0.0,
        market_stress: float = 0.0,
        horizon_days: Optional[int] = None,
    ) -> RiskPrediction:
        """Predict future risk metrics.

        Args:
            current_volatility: Current portfolio volatility (0-1 scale)
            vol_momentum: Rate of change in volatility (-1 to 1)
            correlation_regime: Average pairwise correlation (0-1)
            market_stress: Composite market stress indicator (0-1)
            horizon_days: Forecast horizon in days
        """
        if horizon_days is None:
            horizon_days = self.default_horizon_days

        warnings: List[str] = []

        # Volatility projection
        vol_adjustment = (
            vol_momentum * 0.4
            + correlation_regime * 0.3
            + market_stress * 0.3
        )
        predicted_volatility = current_volatility * (1 + vol_adjustment)
        predicted_volatility = max(0.0, min(predicted_volatility, 1.0))

        # Confidence based on signal strength
        signal_strength = abs(vol_momentum) + correlation_regime + market_stress
        confidence = min(signal_strength / 2.0, 1.0)

        # Trend classification
        delta = predicted_volatility - current_volatility
        if delta > 0.05:
            trend = "increasing"
            warnings.append(
                f"Volatility projected to rise to {predicted_volatility:.1%} "
                f"in {horizon_days} days"
            )
        elif delta < -0.05:
            trend = "decreasing"
        else:
            trend = "stable"

        # Additional warnings
        if predicted_volatility > self.volatility_threshold:
            warnings.append(
                f"Risk Warning: volatility exceeding "
                f"{self.volatility_threshold:.0%} threshold"
            )

        if correlation_regime > 0.7:
            warnings.append(
                "Diversification benefit declining – correlations rising"
            )

        if market_stress > 0.6:
            warnings.append("Market stress elevated – tail risk increasing")

        return RiskPrediction(
            current_volatility=current_volatility,
            predicted_volatility=predicted_volatility,
            forecast_horizon_days=horizon_days,
            confidence=confidence,
            trend=trend,
            warnings=warnings,
        )

    def predict_simple(self, current_volatility: float) -> dict:
        """Simple prediction returning the input as future_risk (legacy)."""
        return {"future_risk": current_volatility}
