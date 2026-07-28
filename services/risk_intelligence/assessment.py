"""Risk Assessment Engine – dynamic multi-dimensional risk evaluation."""

from typing import Dict, List, Optional

from .risk import RiskProfile, classify_risk_level, compute_risk_score


class RiskAssessmentEngine:
    """Evaluates portfolio risk across multiple dimensions.

    Combines exposure, volatility, drawdown, concentration, beta, and
    VaR into a single risk score with factor-level attribution.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights

    def evaluate(
        self,
        exposure: float,
        volatility: float = 0.0,
        drawdown: float = 0.0,
        concentration: float = 0.0,
        beta: float = 0.0,
        var_95: float = 0.0,
        portfolio_id: str = "default",
        custom_factors: Optional[Dict[str, float]] = None,
    ) -> RiskProfile:
        """Evaluate portfolio risk and return a full RiskProfile."""
        score = compute_risk_score(
            exposure=exposure,
            volatility=volatility,
            drawdown=drawdown,
            concentration=concentration,
            beta=beta,
            var_95=var_95,
            weights=self.weights,
        )
        level = classify_risk_level(score)

        # Factor attribution
        factor_attribution: Dict[str, float] = {
            "Exposure": min(exposure, 1.0) * 100,
            "Volatility": min(volatility, 1.0) * 100,
            "Drawdown": min(drawdown, 1.0) * 100,
            "Concentration": min(concentration, 1.0) * 100,
            "Market Beta": max(min(beta, 3.0), 0.0) / 3.0 * 100,
            "VaR (95%)": min(var_95, 1.0) * 100,
        }
        if custom_factors:
            factor_attribution.update(custom_factors)

        # Sort by contribution
        sorted_factors = sorted(
            factor_attribution.items(), key=lambda x: x[1], reverse=True
        )
        factor_attribution = dict(sorted_factors)

        # Identify key risk drivers (top contributors > threshold)
        risk_drivers: List[str] = [
            name for name, contrib in sorted_factors if contrib >= 20
        ]
        if not risk_drivers:
            # Always include top 2 if none exceed threshold
            risk_drivers = [name for name, _ in sorted_factors[:2]]

        return RiskProfile(
            portfolio_id=portfolio_id,
            score=score,
            level=level,
            factor_attribution=factor_attribution,
            risk_drivers=risk_drivers,
            volatility=volatility,
            var_95=var_95,
            max_drawdown=drawdown,
            beta=beta,
            concentration=concentration,
        )

    def evaluate_simple(self, exposure: float) -> float:
        """Simple linear evaluation – for backward compatibility."""
        return exposure * 100
