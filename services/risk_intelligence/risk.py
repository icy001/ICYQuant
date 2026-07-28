"""Risk Model – core risk profile and metrics for portfolio analysis."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RiskProfile:
    """A comprehensive risk profile for a portfolio.

    Contains the overall risk score, level classification, factor-level
    risk attribution breakdown, and a summary of risk drivers.
    """

    portfolio_id: str
    score: float  # 0-100
    level: str  # "low", "medium", "high", "critical"

    # Risk factor attribution (factor_name -> contribution percentage)
    factor_attribution: Dict[str, float] = field(default_factory=dict)

    # Key risk drivers
    risk_drivers: List[str] = field(default_factory=list)

    # Detailed metrics
    volatility: float = 0.0
    var_95: float = 0.0  # Value at Risk 95%
    cvar_95: float = 0.0  # Conditional VaR 95%
    max_drawdown: float = 0.0
    beta: float = 0.0
    sharpe: float = 0.0
    concentration: float = 0.0

    def to_dict(self) -> dict:
        return {
            "portfolio_id": self.portfolio_id,
            "score": self.score,
            "level": self.level,
            "factor_attribution": self.factor_attribution,
            "risk_drivers": self.risk_drivers,
            "volatility": self.volatility,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "max_drawdown": self.max_drawdown,
            "beta": self.beta,
            "sharpe": self.sharpe,
            "concentration": self.concentration,
        }


def classify_risk_level(score: float) -> str:
    """Classify a risk score (0-100) into a level label."""
    if score >= 80:
        return "critical"
    elif score >= 60:
        return "high"
    elif score >= 30:
        return "medium"
    else:
        return "low"


def compute_risk_score(
    exposure: float = 0.0,
    volatility: float = 0.0,
    drawdown: float = 0.0,
    concentration: float = 0.0,
    beta: float = 0.0,
    var_95: float = 0.0,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Compute a weighted composite risk score (0-100).

    Default weights:
        exposure:     20%
        volatility:   25%
        drawdown:     20%
        concentration: 15%
        beta:         10%
        var_95:       10%
    """
    if weights is None:
        weights = {
            "exposure": 0.20,
            "volatility": 0.25,
            "drawdown": 0.20,
            "concentration": 0.15,
            "beta": 0.10,
            "var_95": 0.10,
        }

    score = (
        weights.get("exposure", 0.20) * min(exposure, 1.0) * 100
        + weights.get("volatility", 0.25) * min(volatility, 1.0) * 100
        + weights.get("drawdown", 0.20) * min(drawdown, 1.0) * 100
        + weights.get("concentration", 0.15) * min(concentration, 1.0) * 100
        + weights.get("beta", 0.10) * max(min(beta, 3.0), 0.0) / 3.0 * 100
        + weights.get("var_95", 0.10) * min(var_95, 1.0) * 100
    )

    return round(min(score, 100.0), 2)
