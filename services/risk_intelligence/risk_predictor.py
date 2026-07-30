"""ICYQuant AI Risk Predictor.

Multi-factor risk prediction engine combining market, portfolio,
liquidity, and credit risk signals into a unified risk score.

Output:
    - Risk Score (0-100)
    - Risk Level (LOW / MEDIUM / HIGH / CRITICAL)
    - Factor contributions
    - Actionable recommendations

Usage::

    predictor = RiskPredictor(RiskPredictorConfig())
    result = predictor.predict(market_data, portfolio_data)
    if result.risk_level == RiskLevel.HIGH:
        # Reduce exposure
        ...
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.risk_intelligence.config import (
    RiskPredictorConfig,
    RiskLevel,
)


# ============================================================================
# Data Types
# ============================================================================


@dataclass
class RiskFactors:
    """Individual risk factor scores."""

    market_volatility: float = 0.0   # 0-100
    liquidity_risk: float = 0.0
    credit_risk: float = 0.0
    tail_risk: float = 0.0
    correlation_risk: float = 0.0
    concentration_risk: float = 0.0
    leverage_risk: float = 0.0
    drawdown_risk: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "market_volatility": round(self.market_volatility, 2),
            "liquidity_risk": round(self.liquidity_risk, 2),
            "credit_risk": round(self.credit_risk, 2),
            "tail_risk": round(self.tail_risk, 2),
            "correlation_risk": round(self.correlation_risk, 2),
            "concentration_risk": round(self.concentration_risk, 2),
            "leverage_risk": round(self.leverage_risk, 2),
            "drawdown_risk": round(self.drawdown_risk, 2),
        }


@dataclass
class RiskPrediction:
    """Complete risk prediction result."""

    risk_score: float  # 0-100
    risk_level: RiskLevel
    factors: RiskFactors = field(default_factory=RiskFactors)
    confidence: float = 0.0  # Model confidence
    recommendation: str = ""
    recommended_actions: List[str] = field(default_factory=list)
    predicted_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": round(self.risk_score, 2),
            "risk_level": self.risk_level.value,
            "factors": self.factors.to_dict(),
            "confidence": round(self.confidence, 4),
            "recommendation": self.recommendation,
            "recommended_actions": self.recommended_actions,
            "predicted_at": self.predicted_at.isoformat(),
        }


# ============================================================================
# Risk Predictor
# ============================================================================


class RiskPredictor:
    """AI Risk Predictor.

    Combines multiple risk factors into a unified risk score.
    Uses a weighted scoring model with configurable factor weights.

    Usage::

        predictor = RiskPredictor(RiskPredictorConfig())
        result = predictor.predict(
            returns=market_returns,
            portfolio_weights=weights,
            leverage=1.5,
            current_drawdown=-0.05,
        )
        print(f"Risk Score: {result.risk_score}, Level: {result.risk_level}")
    """

    # Default factor weights
    DEFAULT_WEIGHTS = {
        "market_volatility": 0.20,
        "liquidity_risk": 0.15,
        "credit_risk": 0.05,
        "tail_risk": 0.15,
        "correlation_risk": 0.10,
        "concentration_risk": 0.15,
        "leverage_risk": 0.10,
        "drawdown_risk": 0.10,
    }

    def __init__(self, config: Optional[RiskPredictorConfig] = None) -> None:
        self.config = config or RiskPredictorConfig()
        self._weights = dict(self.DEFAULT_WEIGHTS)
        self._history: List[RiskPrediction] = []

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        returns: Optional[List[float]] = None,
        portfolio_weights: Optional[Dict[str, float]] = None,
        leverage: float = 1.0,
        current_drawdown: float = 0.0,
        bid_ask_spread: float = 0.0,
        vix: Optional[float] = None,
        credit_spread: Optional[float] = None,
        **kwargs: Any,
    ) -> RiskPrediction:
        """Predict the current risk score.

        Args:
            returns: Recent return series.
            portfolio_weights: Portfolio allocation weights.
            leverage: Current portfolio leverage.
            current_drawdown: Current drawdown as fraction (e.g. -0.05).
            bid_ask_spread: Average bid-ask spread.
            vix: VIX or equivalent volatility index.
            credit_spread: Credit spread indicator.
            **kwargs: Additional inputs.

        Returns:
            RiskPrediction with score, level, and recommendations.
        """
        factors = RiskFactors()

        # Market volatility risk
        factors.market_volatility = self._assess_volatility(returns, vix)

        # Liquidity risk
        factors.liquidity_risk = self._assess_liquidity(bid_ask_spread, returns)

        # Credit risk
        factors.credit_risk = self._assess_credit(credit_spread)

        # Tail risk
        factors.tail_risk = self._assess_tail_risk(returns)

        # Correlation risk
        factors.correlation_risk = self._assess_correlation(returns)

        # Concentration risk
        factors.concentration_risk = self._assess_concentration(portfolio_weights)

        # Leverage risk
        factors.leverage_risk = self._assess_leverage(leverage)

        # Drawdown risk
        factors.drawdown_risk = self._assess_drawdown(current_drawdown)

        # Weighted composite score
        risk_score = self._compute_composite(factors)
        risk_level = self._score_to_level(risk_score)

        # Generate recommendation
        recommendation, actions = self._generate_recommendation(
            risk_score, risk_level, factors
        )

        # Confidence estimate
        confidence = self._estimate_confidence(returns, factors)

        prediction = RiskPrediction(
            risk_score=risk_score,
            risk_level=risk_level,
            factors=factors,
            confidence=confidence,
            recommendation=recommendation,
            recommended_actions=actions,
        )

        self._history.append(prediction)
        if len(self._history) > self.config.lookback_window * 2:
            self._history = self._history[-self.config.lookback_window * 2:]

        return prediction

    # ------------------------------------------------------------------
    # Factor Assessment
    # ------------------------------------------------------------------

    def _assess_volatility(
        self, returns: Optional[List[float]], vix: Optional[float]
    ) -> float:
        """Assess market volatility risk (0-100)."""
        if vix is not None:
            # Normalize: VIX 20 = 50, VIX 40 = 100
            return min(100.0, vix / 0.4)

        if returns and len(returns) >= 10:
            vol = self._compute_volatility(returns[-20:])
            # 15% annualized vol = 30, 50% = 100
            return min(100.0, (vol / 0.50) * 100)

        return 25.0

    def _assess_liquidity(
        self, spread: float, returns: Optional[List[float]]
    ) -> float:
        """Assess liquidity risk (0-100)."""
        if spread > 0:
            # 0.1% spread = 10, 1% = 50, 3% = 100
            return min(100.0, (spread / 0.03) * 100)

        return 15.0

    def _assess_credit(self, credit_spread: Optional[float]) -> float:
        """Assess credit risk from credit spreads."""
        if credit_spread is not None and credit_spread > 0:
            return min(100.0, credit_spread * 50)
        return 10.0

    def _assess_tail_risk(self, returns: Optional[List[float]]) -> float:
        """Assess tail risk from return distribution."""
        if not returns or len(returns) < 20:
            return 20.0

        recent = returns[-60:] if len(returns) >= 60 else returns
        vol = self._compute_volatility(recent)
        skew = self._compute_skewness(recent)
        kurt = self._compute_kurtosis(recent)

        # Negative skew + high kurtosis = tail risk
        skew_penalty = max(0, -skew) * 50
        kurt_penalty = max(0, kurt - 3) * 15
        vol_penalty = min(50, vol * 100)

        return min(100.0, skew_penalty + kurt_penalty + vol_penalty * 0.5)

    def _assess_correlation(self, returns: Optional[List[float]]) -> float:
        """Assess correlation / systemic risk."""
        # Simplified: high volatility = higher systemic risk
        if returns and len(returns) >= 10:
            vol = self._compute_volatility(returns[-20:])
            return min(100.0, vol * 150)
        return 20.0

    def _assess_concentration(
        self, weights: Optional[Dict[str, float]]
    ) -> float:
        """Assess portfolio concentration risk."""
        if not weights or len(weights) == 0:
            return 0.0

        values = list(weights.values())
        if sum(values) == 0:
            return 0.0

        # HHI (Herfindahl-Hirschman Index) normalized
        hhi = sum((w / sum(values)) ** 2 for w in values)
        # HHI of 0.2 = 50, HHI of 0.5 = 100
        return min(100.0, hhi * 200)

    def _assess_leverage(self, leverage: float) -> float:
        """Assess leverage risk."""
        if leverage <= 1.0:
            return 0.0
        if leverage >= 5.0:
            return 100.0
        return (leverage - 1.0) * 25

    def _assess_drawdown(self, drawdown: float) -> float:
        """Assess drawdown risk."""
        dd_pct = abs(drawdown) * 100
        return min(100.0, dd_pct * 5)  # 20% DD = 100

    def _compute_composite(self, factors: RiskFactors) -> float:
        """Compute weighted composite risk score."""
        score = 0.0
        total_weight = 0.0

        for name, weight in self._weights.items():
            value = getattr(factors, name, 0.0)
            score += value * weight
            total_weight += weight

        return score / total_weight if total_weight > 0 else 0.0

    def _score_to_level(self, score: float) -> RiskLevel:
        """Convert numerical score to RiskLevel."""
        if score <= self.config.low_risk_threshold:
            return RiskLevel.LOW
        elif score <= self.config.medium_risk_threshold:
            return RiskLevel.MEDIUM
        elif score <= 90:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def _generate_recommendation(
        self, score: float, level: RiskLevel, factors: RiskFactors
    ) -> Tuple[str, List[str]]:
        """Generate human-readable recommendation and actions."""
        actions: List[str] = []

        if level == RiskLevel.LOW:
            recommendation = "Normal conditions. Maintain current positions."
            actions = ["Monitor standard risk metrics"]
        elif level == RiskLevel.MEDIUM:
            recommendation = "Elevated risk. Consider reducing exposure."
            actions = ["Reduce leverage by 25%", "Review concentration limits"]
            if factors.volatility_score > 50:
                actions.append("Hedge tail risk")
        elif level == RiskLevel.HIGH:
            recommendation = "High risk. Reduce exposure immediately."
            actions = [
                "Reduce leverage by 50%",
                "Reduce position sizes by 30%",
                "Increase cash allocation",
                "Activate portfolio hedges",
            ]
            if factors.drawdown_risk > 60:
                actions.append("Stop adding new positions")
        else:
            recommendation = "Critical risk. Emergency action required."
            actions = [
                "Reduce leverage to minimum",
                "Close all discretionary positions",
                "Activate emergency stop protocols",
                "Move to safe-haven assets",
            ]

        return recommendation, actions

    # ------------------------------------------------------------------
    # Statistics Helpers
    # ------------------------------------------------------------------

    def _compute_volatility(self, returns: List[float]) -> float:
        """Compute annualized volatility."""
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        return math.sqrt(max(var, 0) * 252)

    def _compute_skewness(self, returns: List[float]) -> float:
        """Compute skewness of a return series."""
        n = len(returns)
        if n < 3:
            return 0.0
        mean = sum(returns) / n
        m2 = sum((r - mean) ** 2 for r in returns) / n
        m3 = sum((r - mean) ** 3 for r in returns) / n
        if m2 <= 0:
            return 0.0
        return m3 / (m2 ** 1.5)

    def _compute_kurtosis(self, returns: List[float]) -> float:
        """Compute excess kurtosis."""
        n = len(returns)
        if n < 4:
            return 0.0
        mean = sum(returns) / n
        m2 = sum((r - mean) ** 2 for r in returns) / n
        m4 = sum((r - mean) ** 4 for r in returns) / n
        if m2 <= 0:
            return 0.0
        return m4 / (m2 ** 2) - 3

    def _estimate_confidence(
        self,
        returns: Optional[List[float]],
        factors: RiskFactors,
    ) -> float:
        """Estimate prediction confidence based on data quality."""
        if not returns or len(returns) < 10:
            return 0.5
        n = len(returns)
        # More data = more confident
        data_factor = min(1.0, n / self.config.lookback_window)
        # Lower factor dispersion = more confident
        return min(1.0, data_factor * 0.85 + 0.15)

    # ------------------------------------------------------------------
    # History & Stats
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 100) -> List[RiskPrediction]:
        """Get prediction history."""
        return self._history[-limit:]

    def get_trend(self, window: int = 10) -> Dict[str, Any]:
        """Get risk score trend over recent predictions."""
        recent = self._history[-window:]
        if not recent:
            return {"trend": "stable", "change": 0.0}

        scores = [p.risk_score for p in recent]
        if len(scores) >= 2:
            change = scores[-1] - scores[0]
            if change > 5:
                trend = "worsening"
            elif change < -5:
                trend = "improving"
            else:
                trend = "stable"
            return {"trend": trend, "change": round(change, 2), "current": scores[-1]}

        return {"trend": "stable", "change": 0.0}

    def set_factor_weights(self, weights: Dict[str, float]) -> None:
        """Update factor weights."""
        total = sum(weights.values())
        self._weights = {k: v / total for k, v in weights.items()}
